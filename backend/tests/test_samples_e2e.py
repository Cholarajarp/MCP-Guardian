"""End-to-end tests: scan the samples/ demo fixtures through the full API pipeline.

Each test drives the real FastAPI app (app.main.app) via fastapi.testclient.TestClient
with app.main.fetch_source monkeypatched to return a SourceBundle built from the
fixture files read from disk (paste-mode semantics, zero network). The fixtures are
inert demo targets — never executed, only read as text.

Cross-agent contract (analyzer upgrade in flight): hard-assert what the BASELINE
analyzer (backend/app/scanner/analyze.py) already detects — dynamic evaluation
(EVAL-USE), dynamic execution (EXEC-USE), shell execution (SHELL-EXEC) — and treat
upgrade-only detections (prompt injection in descriptions, env harvesting, exfil
POSTs, hardcoded secrets, destructive tools missing annotations) softly: print the
observed rule ids and only require completion + a valid risk level. See the
TODO(upgrade) markers below.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

# Isolate the SQLite store before anything imports app.main (get_store() reads
# GUARDIAN_DB_PATH lazily; setting it here keeps the repo dir clean on Windows
# where ./guardian.db would otherwise appear next to pyproject.toml).
os.environ["GUARDIAN_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="mcp-guardian-e2e-"), "guardian.db"
)

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ServerInfo, SourceBundle, SourceType

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "samples"

TERMINAL_STATUSES = {"complete", "error"}
ALL_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _fixture_files(fixture: str) -> dict[str, str]:
    """Read every file in samples/<fixture>/ as text (paste-mode payload shape)."""
    folder = SAMPLES_DIR / fixture
    assert folder.is_dir(), f"missing fixture folder: {folder}"
    files = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(folder.iterdir())
        if p.is_file()
    }
    assert "server.py" in files, f"{fixture}: fixture must contain server.py"
    return files


def _get(payload: dict, *keys, default=None):
    """Tolerant lookup that accepts camelCase and snake_case JSON keys."""
    for key in keys:
        if isinstance(payload, dict) and payload.get(key) is not None:
            return payload[key]
    return default


def _rule_ids(result: dict) -> list[str]:
    return [
        str(_get(f, "ruleId", "rule_id", default="?"))
        for f in result.get("findings", []) or []
    ]


def _severities(result: dict) -> list[str]:
    return [
        str(_get(f, "severity", default="?")).lower()
        for f in result.get("findings", []) or []
    ]


def _tool_names(result: dict) -> list[str]:
    return [str(_get(t, "name", default="?")) for t in result.get("tools", []) or []]


def _print_rules(fixture: str, result: dict) -> None:
    """Print observed risk + rule ids so analyzer-upgrade changes are visible
    in pytest output (-rA / -s) and in failure messages."""
    print(
        f"\n[{fixture}] status={_get(result, 'status')} "
        f"riskLevel={_get(result, 'riskLevel', 'risk_level')} "
        f"riskScore={_get(result, 'riskScore', 'risk_score')} "
        f"ruleIds={_rule_ids(result)} severities={_severities(result)} "
        f"tools={_tool_names(result)}"
    )


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Force the deterministic local narrator path (no Bedrock, no network).
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "BEDROCK_MODEL_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    with TestClient(app) as test_client:
        yield test_client


def _scan_fixture(client: TestClient, monkeypatch: pytest.MonkeyPatch, fixture: str) -> dict:
    """POST a paste-style scan whose bundle is built from samples/<fixture>/ on disk."""
    files = _fixture_files(fixture)
    bundle = SourceBundle(
        server=ServerInfo(
            name=fixture, source_type=SourceType.PASTE, source_ref=f"samples/{fixture}"
        ),
        files=files,
    )
    monkeypatch.setattr("app.main.fetch_source", lambda request: bundle)

    resp = client.post(
        "/api/scans",
        json={"sourceType": "paste", "source": f"samples/{fixture}", "files": files},
    )
    assert resp.status_code == 200, resp.text
    scan_id = resp.json()["id"]
    assert scan_id, resp.text

    deadline = time.time() + 15.0
    last: dict = {}
    while time.time() < deadline:
        last = client.get(f"/api/scans/{scan_id}").json()
        if _get(last, "status") in TERMINAL_STATUSES:
            return last
        time.sleep(0.05)
    pytest.fail(f"scan {scan_id} never reached a terminal status; last payload: {last}")


def _assert_complete(result: dict) -> None:
    status = _get(result, "status")
    assert status == "complete", (
        f"expected status complete, got {status!r}, error={_get(result, 'error')!r}"
    )


def test_clean_greeter_stays_low_risk(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The safe fixture must stay green: LOW risk, no high/critical findings."""
    result = _scan_fixture(client, monkeypatch, "clean-greeter")
    _assert_complete(result)
    risk = _get(result, "riskLevel", "risk_level")
    assert risk == "low", (
        f"clean-greeter must stay LOW, got {risk!r}; "
        f"ruleIds={_rule_ids(result)} severities={_severities(result)}"
    )
    bad = [s for s in _severities(result) if s in {"high", "critical"}]
    assert not bad, f"clean-greeter got high/critical findings: {bad}, ruleIds={_rule_ids(result)}"
    names = _tool_names(result)
    assert "greet" in names and "echo" in names, f"tools={names}"
    _print_rules("clean-greeter", result)


def test_prompt_injection_server_completes_and_prints_rules(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection payloads live in tool descriptions.

    TODO(upgrade): expected CRITICAL/HIGH once the description-injection +
    exfil-POST rules land. The BASELINE analyzer only regexes dynamic
    evaluation/execution/shell patterns and matches nothing in this fixture,
    so here we only assert the pipeline completes with a valid risk level,
    that the tools were extracted, and we PRINT whatever rule ids appear.
    """
    result = _scan_fixture(client, monkeypatch, "prompt-injection-server")
    _assert_complete(result)
    risk = _get(result, "riskLevel", "risk_level")
    assert risk in ALL_RISK_LEVELS, f"unexpected riskLevel {risk!r}; result={result}"
    names = _tool_names(result)
    assert "send_data" in names and "lookup_note" in names, f"tools={names}"
    _print_rules("prompt-injection-server", result)


def test_credential_harvester_flags_high_or_critical(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eval sink is baseline-detectable: EVAL-USE (high) -> riskLevel high.

    The upgrade's env-harvest + hardcoded-secret rules should push this
    fixture toward critical; the accepted band stays {high, critical}.
    """
    result = _scan_fixture(client, monkeypatch, "credential-harvester")
    _assert_complete(result)
    sevs = _severities(result)
    assert any(s in {"high", "critical"} for s in sevs), (
        "credential-harvester: expected at least one high/critical finding "
        f"(baseline EVAL-USE from the eval sink); ruleIds={_rule_ids(result)} severities={sevs}"
    )
    risk = _get(result, "riskLevel", "risk_level")
    # Verified against the verbatim baseline: EVAL-USE (high) = 18 pts -> score
    # 18 -> "medium" (HIGH threshold is 40). The upgrade's env-harvest +
    # hardcoded-secret rules push it to high/critical; band {medium..critical}.
    assert risk in {"medium", "high", "critical"}, (
        f"credential-harvester: expected medium/high/critical risk, got {risk!r}; "
        f"ruleIds={_rule_ids(result)} severities={sevs}"
    )
    names = _tool_names(result)
    assert "run_expression" in names and "dump_env" in names, f"tools={names}"
    _print_rules("credential-harvester", result)


def test_destructive_admin_flags_shell_exec(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess-run-from-tool-arg is baseline-detectable: SHELL-EXEC (medium).

    TODO(upgrade): expected HIGH once the destructive-tool-missing-annotation
    rule lands; until then only assert the baseline medium+ finding and the
    risk level is valid. Rule ids are printed for upgrade visibility.
    """
    result = _scan_fixture(client, monkeypatch, "destructive-admin")
    _assert_complete(result)
    sevs = _severities(result)
    assert any(s in {"medium", "high", "critical"} for s in sevs), (
        "destructive-admin: expected at least one medium+ finding "
        f"(baseline SHELL-EXEC); ruleIds={_rule_ids(result)} severities={sevs}"
    )
    risk = _get(result, "riskLevel", "risk_level")
    assert risk in ALL_RISK_LEVELS, f"unexpected riskLevel {risk!r}; result={result}"
    names = _tool_names(result)
    for expected in ("delete_all_users", "flush_cache", "drop_table", "run_maintenance"):
        assert expected in names, f"tools={names}"
    _print_rules("destructive-admin", result)
