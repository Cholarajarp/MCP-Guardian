"""Persistence for scan results. SQLite. Owned by backend-core agent.

Hardened version:
- WAL journal + busy_timeout, so the background scan writer never blocks API readers.
- Every access is serialized through one re-entrant lock (race-safe across the
  API threads and the background scan threads sharing a single connection).
- Index on created_at for newest-first listing; rowid as a deterministic tie-break.
- ``update_status`` also rewrites the stored payload, so GET /api/scans/{id}
  never reports a stale status after a status-only transition.
- Lazy auto-init: all methods work even if ``init()`` was never called.
- ``list_recent`` clamps the limit (0 <= limit <= 200) and orders newest first.
The Store protocol and ``get_store()`` factory are unchanged (locked contract).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol

from app.models import ScanResult, ScanStatus


class Store(Protocol):
    def init(self) -> None: ...
    def save(self, result: ScanResult) -> None: ...
    def get(self, scan_id: str) -> Optional[ScanResult]: ...
    def update_status(self, scan_id: str, status: ScanStatus) -> None: ...
    def list_recent(self, limit: int = 50) -> list[ScanResult]: ...


_MAX_LIST_LIMIT = 200

# Pagination ceiling for DynamoDB history reads. One scan() call returns at most
# 1 MB, so pagination is required for correct "newest first" ordering — but an
# unbounded follow would let a large table turn one API request into a large
# read bill. 10 pages is far more than the demo needs and still bounded.
_MAX_SCAN_PAGES = 10

# Scan rows self-delete after this many days (DynamoDB TTL on `expires_at`),
# so history cannot grow without limit on the always-free 25 GB tier.
_SCAN_TTL_DAYS = 30


def _ttl_epoch(days: int) -> int:
    """Unix epoch seconds `days` from now — the format DynamoDB TTL expects."""
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())


class SQLiteStore:
    def __init__(self, path: str = "./guardian.db") -> None:
        self._path = path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None

    # -- lifecycle ----------------------------------------------------------
    def init(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            conn = sqlite3.connect(self._path, check_same_thread=False, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS scans (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scans_created ON scans (created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scans_status ON scans (status)")
            conn.commit()
            self._conn = conn

    def close(self) -> None:
        """Release the connection (used by tests; safe to call repeatedly)."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _conn_ready(self) -> sqlite3.Connection:
        if self._conn is None:
            self.init()
        assert self._conn is not None
        return self._conn

    # -- Store protocol -----------------------------------------------------
    def save(self, result: ScanResult) -> None:
        conn = self._conn_ready()
        payload = result.model_dump_json(by_alias=True)
        with self._lock:
            conn.execute(
                "INSERT INTO scans (id, status, created_at, payload) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status = excluded.status, "
                "created_at = excluded.created_at, payload = excluded.payload",
                (result.id, result.status.value, result.created_at.isoformat(), payload),
            )
            conn.commit()

    def get(self, scan_id: str) -> Optional[ScanResult]:
        conn = self._conn_ready()
        with self._lock:
            row = conn.execute("SELECT payload FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return ScanResult.model_validate_json(row[0]) if row else None

    def update_status(self, scan_id: str, status: ScanStatus) -> None:
        conn = self._conn_ready()
        with self._lock:
            row = conn.execute("SELECT payload FROM scans WHERE id = ?", (scan_id,)).fetchone()
            if row is None:
                return
            data = json.loads(row[0])
            data["status"] = status.value  # "status" is identical in snake_case and camelCase
            conn.execute(
                "UPDATE scans SET status = ?, payload = ? WHERE id = ?",
                (status.value, json.dumps(data), scan_id),
            )
            conn.commit()

    def list_recent(self, limit: int = 50) -> list[ScanResult]:
        conn = self._conn_ready()
        try:
            lim = int(limit)
        except (TypeError, ValueError):
            lim = 50
        lim = max(0, min(lim, _MAX_LIST_LIMIT))
        with self._lock:
            rows = conn.execute(
                "SELECT payload FROM scans ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (lim,),
            ).fetchall()
        return [ScanResult.model_validate_json(r[0]) for r in rows]


class DynamoDBStore:
    """DynamoDB-backed store for Lambda deploys (table keyed by `id`).

    Enabled when SCANS_TABLE_NAME is set — Lambda /tmp is ephemeral, so the
    deployed demo persists scan history in DynamoDB (always-free tier covers
    25 GB; this workload uses kilobytes). The table is provisioned by
    infra/template.yaml.
    """

    def __init__(self, table_name: str, region: str | None = None) -> None:
        self._table_name = table_name
        self._region = region
        self._table = None

    def _table_ref(self):
        if self._table is None:
            import boto3  # noqa: PLC0415 — only needed in deployed mode

            resource = boto3.resource(
                "dynamodb", region_name=self._region or os.environ.get("AWS_REGION", "us-east-1")
            )
            self._table = resource.Table(self._table_name)
        return self._table

    def init(self) -> None:
        self._table_ref()  # fail fast on missing table/permissions

    def save(self, result: ScanResult) -> None:
        self._table_ref().put_item(
            Item={"id": result.id, "created_at": result.created_at.isoformat(),
                  "payload": result.model_dump_json(by_alias=True),
                  "expires_at": _ttl_epoch(_SCAN_TTL_DAYS)}
        )

    def get(self, scan_id: str) -> Optional[ScanResult]:
        item = self._table_ref().get_item(Key={"id": scan_id}).get("Item")
        if not item or "payload" not in item:
            # The table is shared with guard bookkeeping rows (budget#...,
            # narrative#...), which carry no payload. Treating one as a scan
            # would raise instead of returning a clean 404.
            return None
        return ScanResult.model_validate_json(item["payload"])

    def update_status(self, scan_id: str, status: ScanStatus) -> None:
        item = self._table_ref().get_item(Key={"id": scan_id}).get("Item")
        if item is None or "payload" not in item:
            return  # missing, or a guard bookkeeping row — never a scan
        data = json.loads(item["payload"])
        data["status"] = status.value
        self._table_ref().put_item(
            Item={"id": scan_id, "created_at": item.get("created_at", data.get("createdAt", "")),
                  "payload": json.dumps(data),
                  # put_item REPLACES the whole row, so the TTL must be
                  # rewritten here or a status transition would strip
                  # expires_at and make the row immortal.
                  "expires_at": _ttl_epoch(_SCAN_TTL_DAYS)}
        )

    def list_recent(self, limit: int = 50) -> list[ScanResult]:
        try:
            lim = int(limit)
        except (TypeError, ValueError):
            lim = 50
        lim = max(0, min(lim, _MAX_LIST_LIMIT))
        if lim == 0:
            return []

        # Two things this has to get right:
        #  1. The table is shared with guard bookkeeping rows (budget#...,
        #     narrative#...). They carry no `payload`, so a blind scan would
        #     raise KeyError. FilterExpression drops them server-side.
        #  2. A single scan() call returns at most 1 MB, so without pagination
        #     "newest first" would silently be "newest within page one". We
        #     follow LastEvaluatedKey, but cap the pages so a growing table can
        #     never turn one request into an unbounded read bill.
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415 — deployed mode only

        table = self._table_ref()
        items: list[dict] = []
        kwargs: dict = {"FilterExpression": Attr("payload").exists()}
        for _page in range(_MAX_SCAN_PAGES):
            response = table.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key

        items.sort(key=lambda i: str(i.get("created_at", "")), reverse=True)
        results: list[ScanResult] = []
        for item in items[:lim]:
            try:
                results.append(ScanResult.model_validate_json(item["payload"]))
            except Exception:  # noqa: BLE001 — one corrupt row must not break history
                continue
        return results


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        table = os.environ.get("SCANS_TABLE_NAME", "").strip()
        if table:
            _store = DynamoDBStore(table)
        else:
            _store = SQLiteStore(os.environ.get("GUARDIAN_DB_PATH", "./guardian.db"))
    return _store
