"""API tests — fully hermetic: fetch/analyze/cedar/narrator are monkeypatched,
so no test touches the network. Uses fastapi.testclient.TestClient."""
from __future__ import annotations

import importlib
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
import app.store as store_mod
from app.models import (
    AnalysisResult,
    Finding,
    RiskLevel,
    ScanRequest,
    ScanResult,
    ScanStatus,
    ServerInfo,
    Severity,
    SourceBundle,
    SourceType,
    ToolInfo,
)


# --- helpers ------------------------------------------------------------------
def _paste_payload() -> dict:
    return {
        "sourceType": "paste",
        "source": "demo-server",
        "files": {"server.py": "@tool\ndef echo(x):\n    return x"},
    }


def _fake_bundle() -> SourceBundle:
    return SourceBundle(
        server=ServerInfo(name="demo-server", source_type=SourceType.PASTE, source_ref="demo-server"),
        files={"server.py": "@tool\ndef echo(x):\n    return x"},
    )


def _scan_result(scan_id: str, *, created_at: datetime, risk_score: int = 0) -> ScanResult:
    return ScanResult(
        id=scan_id,
        status=ScanStatus.COMPLETE,
        request=ScanRequest(source_type=SourceType.PASTE, source="demo", files={"a.py": "x"}),
        server=ServerInfo(name="demo", source_type=SourceType.PASTE, source_ref="demo"),
        risk_score=risk_score,
        created_at=created_at,
    )


def _await_status(client: TestClient, scan_id: str, statuses: set[str], timeout: float = 10.0) -> dict:
    """Poll GET /api/scans/{id} until the background thread lands a terminal status."""
    deadline = time.time() + timeout
    body: dict = {}
    while time.time() < deadline:
        resp = client.get(f"/api/scans/{scan_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in statuses:
            return body
        time.sleep(0.05)
    pytest.fail(f"scan {scan_id} never reached {statuses}; last body: {body}")


# --- fixtures -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """Point the store singleton at a temp DB for every test (no repo files)."""
    monkeypatch.setenv("GUARDIAN_DB_PATH", str(tmp_path / "api-test.db"))
    previous = store_mod._store
    store_mod._store = None
    yield
    if isinstance(store_mod._store, store_mod.SQLiteStore):
        store_mod._store.close()
    store_mod._store = previous


@pytest.fixture()
def client():
    with TestClient(main_mod.app) as c:  # context manager triggers lifespan (store init)
        yield c


@pytest.fixture()
def patched_pipeline(monkeypatch):
    """Replace the whole scan pipeline with deterministic offline stubs."""
    def fake_fetch(request: ScanRequest) -> SourceBundle:
        return _fake_bundle()

    def fake_analyze(bundle: SourceBundle) -> AnalysisResult:
        return AnalysisResult(
            findings=[
                Finding(
                    id="f1",
                    rule_id="EVAL-USE",
                    title="Dynamic eval()",
                    severity=Severity.HIGH,
                    description="uses eval",
                    remediation="remove it",
                )
            ],
            tools=[ToolInfo(name="echo", description="echoes", annotations=[], risks=[])],
            risk_score=42,
            risk_level=RiskLevel.MEDIUM,
            summary="one tool, one finding",
        )

    monkeypatch.setattr(main_mod, "fetch_source", fake_fetch)
    monkeypatch.setattr(main_mod, "analyze_bundle", fake_analyze)
    monkeypatch.setattr(main_mod, "generate_cedar_policy", lambda server, analysis: "namespace Demo {}")
    monkeypatch.setattr(main_mod, "generate_narrative", lambda server, analysis: "narrative text")


# --- tests -----------------------------------------------------------------------
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "mcp-guardian"


def test_paste_scan_happy_path(client, patched_pipeline):
    resp = client.post("/api/scans", json=_paste_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"id"}
    scan_id = body["id"]
    assert isinstance(scan_id, str) and 8 <= len(scan_id) <= 32

    result = _await_status(client, scan_id, {"complete"})
    # camelCase contract
    assert set(result) >= {
        "id", "status", "request", "server", "riskScore", "riskLevel",
        "findings", "tools", "cedarPolicy", "narrative", "createdAt", "durationMs",
    }
    assert result["id"] == scan_id
    assert result["riskScore"] == 42
    assert result["riskLevel"] == "medium"
    assert result["request"]["sourceType"] == "paste"
    assert result["request"]["files"]["server.py"].startswith("@tool")
    assert result["server"]["name"] == "demo-server"
    assert result["findings"][0]["ruleId"] == "EVAL-USE"
    assert result["findings"][0]["severity"] == "high"
    assert result["tools"][0]["name"] == "echo"
    assert result["cedarPolicy"] == "namespace Demo {}"
    assert result["narrative"] == "narrative text"
    assert isinstance(result["durationMs"], int)
    assert result["error"] is None


def test_github_scan_happy_path(client, patched_pipeline):
    resp = client.post(
        "/api/scans", json={"sourceType": "github", "source": "octo/demo", "ref": "main"}
    )
    assert resp.status_code == 200
    result = _await_status(client, resp.json()["id"], {"complete"})
    assert result["request"]["sourceType"] == "github"
    assert result["request"]["ref"] == "main"
    assert result["server"]["name"] == "demo-server"


def test_paste_without_files_returns_422(client):
    resp = client.post("/api/scans", json={"sourceType": "paste", "source": "x"})
    assert resp.status_code == 422
    assert "files" in resp.json()["detail"]


def test_paste_with_empty_files_returns_422(client):
    resp = client.post("/api/scans", json={"sourceType": "paste", "source": "x", "files": {}})
    assert resp.status_code == 422


def test_invalid_source_type_returns_422(client):
    resp = client.post("/api/scans", json={"sourceType": "ftp", "source": "x"})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_missing_fields_return_422(client):
    resp = client.post("/api/scans", json={"sourceType": "github"})
    assert resp.status_code == 422


def test_blank_source_returns_422(client):
    resp = client.post("/api/scans", json={"sourceType": "github", "source": "   "})
    assert resp.status_code == 422
    assert "source" in resp.json()["detail"]


def test_oversized_source_returns_422(client):
    resp = client.post("/api/scans", json={"sourceType": "github", "source": "a" * 600})
    assert resp.status_code == 422


def test_get_unknown_scan_returns_404(client):
    resp = client.get("/api/scans/does-not-exist")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_list_scans_newest_first_with_camel_case(client, patched_pipeline):
    store = store_mod.get_store()
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(3):
        store.save(_scan_result(f"seed-{i}", created_at=base + timedelta(seconds=i), risk_score=i))

    created = client.post("/api/scans", json=_paste_payload()).json()["id"]
    _await_status(client, created, {"complete"})

    resp = client.get("/api/scans?limit=50")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 4
    assert items[0]["id"] == created  # the freshest scan first
    assert [items[1]["riskScore"], items[2]["riskScore"], items[3]["riskScore"]] == [2, 1, 0]
    assert "riskScore" in items[0] and "cedarPolicy" in items[0]


def test_list_scans_limit_validated(client):
    assert client.get("/api/scans?limit=0").status_code == 422
    assert client.get("/api/scans?limit=500").status_code == 422
    assert client.get("/api/scans").status_code == 200


def test_scan_failure_becomes_error_status(client, monkeypatch):
    def boom(request: ScanRequest) -> SourceBundle:
        raise RuntimeError("github API unreachable")

    monkeypatch.setattr(main_mod, "fetch_source", boom)
    resp = client.post("/api/scans", json={"sourceType": "github", "source": "octo/demo"})
    scan_id = resp.json()["id"]
    result = _await_status(client, scan_id, {"error"})
    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
    assert "github API unreachable" in result["error"]
    assert isinstance(result["durationMs"], int)


def test_double_submit_creates_distinct_safe_scans(client, patched_pipeline):
    ids = []
    for _ in range(2):
        resp = client.post("/api/scans", json=_paste_payload())
        assert resp.status_code == 200
        ids.append(resp.json()["id"])
    assert len(set(ids)) == 2
    for scan_id in ids:
        result = _await_status(client, scan_id, {"complete"})
        assert result["riskScore"] == 42


def test_default_cors_allows_local_frontend(client):
    pre = client.options(
        "/api/scans",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert pre.status_code in (200, 204)
    assert pre.headers.get("access-control-allow-origin") == "http://localhost:3000"

    pre_bad = client.options(
        "/api/scans",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in pre_bad.headers


def test_allowed_origins_env_respected(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://good.example,http://also.example")
    try:
        importlib.reload(main_mod)
        with TestClient(main_mod.app) as reloaded:
            ok = reloaded.options(
                "/api/scans",
                headers={"Origin": "https://good.example", "Access-Control-Request-Method": "POST"},
            )
            bad = reloaded.options(
                "/api/scans",
                headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
            )
        assert ok.headers.get("access-control-allow-origin") == "https://good.example"
        assert "access-control-allow-origin" not in bad.headers
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        importlib.reload(main_mod)  # restore pristine module state for other tests
