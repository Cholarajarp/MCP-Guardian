"""Abuse and cost guards for the public deployment.

The deployed demo answers on a Lambda Function URL with ``AuthType: NONE``, and
every completed scan can invoke Amazon Bedrock -- the only paid API in the whole
stack. Without a ceiling, a single scripted client decides how much Nova costs.
Three independent guards live here:

* ``check_scan_rate`` -- per-client sliding-window limit on scan creation.
  In-memory, therefore per Lambda instance: a speed bump against scripted abuse
  rather than a distributed quota. Combined with reserved concurrency it bounds
  how fast work can enter the system at all.

* ``try_consume_narrative_budget`` -- a hard global ceiling on paid Bedrock
  calls per UTC day, kept as an atomic DynamoDB counter so every Lambda instance
  shares one budget. Once spent, narration falls back to the deterministic
  template: the product keeps working and the bill stops.

* ``narrative_cache_get`` / ``narrative_cache_put`` -- content-addressed reuse of
  generated narratives, so re-scanning an unchanged server is free after the
  first time.

Failure policy: the DynamoDB-backed guards degrade to per-instance accounting
(and log) when the table is unreachable, because a store outage must not
uncap spend, yet must not take the product offline either. The in-memory
per-client limiter has no external dependency and therefore always applies.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("mcp_guardian.guard")


# --- configuration ----------------------------------------------------------
# Every limit is read at call time, never cached at import, so deployments and
# tests can change behaviour through the environment alone.

def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        logger.warning("invalid %s=%r; using %d", name, raw, default)
        value = default
    return max(minimum, min(value, maximum))


def _rate_limit() -> int:
    """Scans allowed per client per window. 0 disables the limiter."""
    return _env_int("SCAN_RATE_LIMIT", 20, 0, 10000)


def _rate_window_seconds() -> int:
    return _env_int("SCAN_RATE_WINDOW_SECONDS", 3600, 1, 86400)


def _daily_narrative_budget() -> int:
    """Max paid Bedrock calls per UTC day across all instances. 0 disables
    narration entirely (template only) -- the absolute zero-cost setting."""
    return _env_int("BEDROCK_DAILY_BUDGET", 500, 0, 1000000)


# --- per-client rate limiting (in-memory, per instance) ---------------------
_hits: dict[str, deque] = {}
_hits_lock = threading.Lock()
_MAX_TRACKED_CLIENTS = 10000


class RateLimited(Exception):
    """Raised when a client exceeds the scan-creation rate limit."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"rate limit exceeded; retry in {retry_after}s")
        self.retry_after = retry_after


def reset_rate_limits() -> None:
    """Drop all rate-limit state (used by tests)."""
    with _hits_lock:
        _hits.clear()


def check_scan_rate(client_id: str) -> None:
    """Record a scan attempt for ``client_id``; raise ``RateLimited`` if over.

    Sliding window: entries older than the window are discarded on each call, so
    there is no cleanup task and no fixed-window burst edge at the boundary.
    """
    limit = _rate_limit()
    if limit <= 0:
        return
    window = _rate_window_seconds()
    now = time.monotonic()
    key = client_id or "unknown"

    with _hits_lock:
        bucket = _hits.get(key)
        if bucket is None:
            # Bound memory: a flood of unique client ids (spoofed
            # X-Forwarded-For) must not grow this dict without limit.
            if len(_hits) >= _MAX_TRACKED_CLIENTS:
                _hits.clear()
            bucket = deque()
            _hits[key] = bucket

        cutoff = now - window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window - now) + 1)
            raise RateLimited(retry_after)

        bucket.append(now)


# --- shared DynamoDB access for the budget + cache --------------------------
_table = None
_table_lock = threading.Lock()


def _table_ref():
    """Lazily resolve the DynamoDB table, or None when not deployed."""
    global _table
    name = os.environ.get("SCANS_TABLE_NAME", "").strip()
    if not name:
        return None
    with _table_lock:
        if _table is None:
            import boto3  # noqa: PLC0415 -- deployed mode only

            resource = boto3.resource(
                "dynamodb", region_name=os.environ.get("AWS_REGION") or "us-east-1"
            )
            _table = resource.Table(name)
        return _table


def _reset_table_cache() -> None:
    """Forget the cached table handle (used by tests)."""
    global _table
    with _table_lock:
        _table = None


def _ttl_epoch(days: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())


# --- global daily Bedrock budget -------------------------------------------
_local_budget_used: dict[str, int] = {}
_local_budget_lock = threading.Lock()


def _budget_key() -> str:
    return f"budget#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def _consume_local_budget(limit: int) -> bool:
    """Single-instance budget accounting (local dev, or DynamoDB unreachable)."""
    key = _budget_key()
    with _local_budget_lock:
        used = _local_budget_used.get(key, 0)
        if used >= limit:
            return False
        # Keep only today's counter so this dict cannot grow over time.
        _local_budget_used.clear()
        _local_budget_used[key] = used + 1
        return True


def reset_narrative_budget() -> None:
    """Drop local budget accounting (used by tests)."""
    with _local_budget_lock:
        _local_budget_used.clear()


def try_consume_narrative_budget() -> bool:
    """Reserve one paid Bedrock call. False means "use the template instead".

    Deployed, this is an atomic DynamoDB ADD guarded by a condition on the
    resulting value, so concurrent Lambda instances cannot jointly overshoot the
    ceiling. The counter row carries a TTL, so old budget rows self-delete.
    """
    limit = _daily_narrative_budget()
    if limit <= 0:
        return False

    table = _table_ref()
    if table is None:
        return _consume_local_budget(limit)

    try:
        table.update_item(
            Key={"id": _budget_key()},
            UpdateExpression="SET expires_at = :ttl ADD used :one",
            ConditionExpression="attribute_not_exists(used) OR used < :limit",
            ExpressionAttributeValues={":one": 1, ":limit": limit, ":ttl": _ttl_epoch(2)},
        )
        return True
    except Exception as exc:  # noqa: BLE001 -- includes ConditionalCheckFailed
        if "ConditionalCheckFailed" in type(exc).__name__:
            logger.warning("daily Bedrock budget of %d reached; using template", limit)
            return False
        # Store trouble must not uncap spend: fall back to per-instance
        # accounting, which still enforces a ceiling per Lambda instance.
        logger.warning(
            "budget counter unavailable (%s); using local accounting", type(exc).__name__
        )
        return _consume_local_budget(limit)


# --- narrative cache --------------------------------------------------------
def narrative_cache_key(source_ref: str, risk_score: int, rule_ids: list) -> str:
    """Content address for a narrative: same server + same findings -> same key.

    The model only sees the server reference, the score and the findings, so
    those inputs are exactly what the key must cover.
    """
    digest = hashlib.sha256()
    digest.update(source_ref.encode("utf-8", errors="replace"))
    digest.update(b"\x00")
    digest.update(str(risk_score).encode("ascii"))
    digest.update(b"\x00")
    for rule_id in sorted(rule_ids):
        digest.update(rule_id.encode("utf-8", errors="replace"))
        digest.update(b"\x00")
    return f"narrative#{digest.hexdigest()[:32]}"


def narrative_cache_get(key: str) -> Optional[str]:
    table = _table_ref()
    if table is None:
        return None
    try:
        item = table.get_item(Key={"id": key}).get("Item")
        text = item.get("narrative") if item else None
        return str(text) if text else None
    except Exception as exc:  # noqa: BLE001 -- a cache miss is always safe
        logger.warning("narrative cache read failed (%s)", type(exc).__name__)
        return None


def narrative_cache_put(key: str, narrative: str) -> None:
    table = _table_ref()
    if table is None or not narrative:
        return
    try:
        table.put_item(
            Item={"id": key, "narrative": narrative, "expires_at": _ttl_epoch(30)}
        )
    except Exception as exc:  # noqa: BLE001 -- caching is best effort
        logger.warning("narrative cache write failed (%s)", type(exc).__name__)
