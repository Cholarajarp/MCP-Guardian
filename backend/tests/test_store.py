"""Store tests — hermetic (SQLite temp files only, no network)."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Finding,
    ScanRequest,
    ScanResult,
    ScanStatus,
    ServerInfo,
    Severity,
    SourceType,
    ToolInfo,
)
from app.store import SQLiteStore, get_store


def _scan_result(
    scan_id: str,
    *,
    status: ScanStatus = ScanStatus.COMPLETE,
    created_at: datetime | None = None,
    risk_score: int = 0,
) -> ScanResult:
    return ScanResult(
        id=scan_id,
        status=status,
        request=ScanRequest(source_type=SourceType.PASTE, source="demo", files={"server.py": "x"}),
        server=ServerInfo(name="demo", source_type=SourceType.PASTE, source_ref="demo"),
        risk_score=risk_score,
        created_at=created_at or datetime.now(timezone.utc),
    )


@pytest.fixture()
def store(tmp_path):
    st = SQLiteStore(str(tmp_path / "test.db"))
    st.init()
    yield st
    st.close()


def test_save_get_roundtrip_preserves_contract(store):
    result = _scan_result("scan-1", risk_score=42)
    result.findings = [
        Finding(
            id="f1",
            rule_id="EVAL-USE",
            title="eval()",
            severity=Severity.HIGH,
            description="uses eval",
            remediation="remove it",
        )
    ]
    result.tools = [ToolInfo(name="echo", description="echoes", annotations=[], risks=[])]
    result.cedar_policy = "namespace Demo {}"
    result.narrative = "narrative text"
    store.save(result)

    got = store.get("scan-1")
    assert got is not None
    assert got.model_dump() == result.model_dump()
    # camelCase JSON contract survives persistence
    as_json = got.model_dump(by_alias=True)
    assert as_json["riskScore"] == 42
    assert as_json["request"]["sourceType"] == "paste"
    assert as_json["findings"][0]["ruleId"] == "EVAL-USE"


def test_get_unknown_returns_none(store):
    assert store.get("nope") is None


def test_save_is_an_upsert(store):
    store.save(_scan_result("scan-1", status=ScanStatus.PENDING))
    updated = _scan_result("scan-1", status=ScanStatus.COMPLETE, risk_score=77)
    store.save(updated)
    got = store.get("scan-1")
    assert got is not None
    assert got.status == ScanStatus.COMPLETE
    assert got.risk_score == 77
    assert len(store.list_recent(50)) == 1


def test_update_status_persists_into_payload(store):
    store.save(_scan_result("scan-1", status=ScanStatus.PENDING))
    store.update_status("scan-1", ScanStatus.SCANNING)
    got = store.get("scan-1")
    assert got is not None
    assert got.status == ScanStatus.SCANNING


def test_update_status_unknown_id_is_noop(store):
    store.update_status("ghost", ScanStatus.SCANNING)  # must not raise
    assert store.get("ghost") is None


def test_list_recent_newest_first_and_limit(store):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(5):
        store.save(_scan_result(f"s{i}", created_at=base + timedelta(seconds=i), risk_score=i))
    recent = store.list_recent(3)
    assert [r.id for r in recent] == ["s4", "s3", "s2"]


def test_list_recent_clamps_bad_limits(store):
    store.save(_scan_result("only"))
    assert store.list_recent(0) == []
    assert store.list_recent(-5) == []
    assert len(store.list_recent(10**9)) == 1


def test_works_without_explicit_init(tmp_path):
    st = SQLiteStore(str(tmp_path / "lazy.db"))
    st.save(_scan_result("lazy-1"))  # no init() call — must auto-init
    got = st.get("lazy-1")
    assert got is not None
    assert got.id == "lazy-1"
    st.close()


def test_init_is_idempotent(store):
    store.init()
    store.init()
    store.save(_scan_result("still-works"))
    assert store.get("still-works") is not None


def test_concurrent_access_is_race_safe(tmp_path):
    st = SQLiteStore(str(tmp_path / "race.db"))
    st.init()
    errors: list[BaseException] = []
    base = datetime.now(timezone.utc)

    def worker(tid: int) -> None:
        try:
            for i in range(25):
                st.save(_scan_result(f"t{tid}-{i}", created_at=base + timedelta(seconds=i), risk_score=i))
                st.get("t0-0")  # interleaved reads
                st.list_recent(5)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(st.list_recent(500)) == 200  # every write survived
    st.close()


def test_get_store_uses_env_path(tmp_path, monkeypatch):
    import app.store as store_mod

    db_path = tmp_path / "env.db"
    monkeypatch.setenv("GUARDIAN_DB_PATH", str(db_path))
    previous = store_mod._store
    store_mod._store = None
    try:
        st = get_store()
        assert isinstance(st, SQLiteStore)
        st.save(_scan_result("env-1"))
        assert db_path.exists()
    finally:
        if isinstance(store_mod._store, SQLiteStore):
            store_mod._store.close()
        store_mod._store = previous
