"""Tests for app/guard.py -- the rate limiter, Bedrock budget and narrative cache.

These guard the only paid API in the stack, so the failure modes that matter are
the silent ones: a limiter that can be bypassed, a budget that overshoots, and a
cache key that changes when it should not.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import guard
from app.main import app


# --- rate limiter -----------------------------------------------------------
def test_rate_limit_allows_up_to_the_configured_limit(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "3")
    for _ in range(3):
        guard.check_scan_rate("1.2.3.4")  # must not raise


def test_rate_limit_blocks_past_the_limit(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "2")
    guard.check_scan_rate("1.2.3.4")
    guard.check_scan_rate("1.2.3.4")
    with pytest.raises(guard.RateLimited) as excinfo:
        guard.check_scan_rate("1.2.3.4")
    assert excinfo.value.retry_after > 0


def test_rate_limit_is_per_client(monkeypatch):
    """One noisy client must not throttle everyone else."""
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    guard.check_scan_rate("1.1.1.1")
    guard.check_scan_rate("2.2.2.2")  # different client, still allowed
    with pytest.raises(guard.RateLimited):
        guard.check_scan_rate("1.1.1.1")


def test_rate_limit_zero_disables_the_limiter(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "0")
    for _ in range(50):
        guard.check_scan_rate("1.2.3.4")


def test_rate_limit_window_expiry_frees_the_bucket(monkeypatch):
    """A sliding window must forget old hits, not just count forever."""
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    monkeypatch.setenv("SCAN_RATE_WINDOW_SECONDS", "1")

    clock = {"now": 1000.0}
    monkeypatch.setattr(guard.time, "monotonic", lambda: clock["now"])

    guard.check_scan_rate("1.2.3.4")
    with pytest.raises(guard.RateLimited):
        guard.check_scan_rate("1.2.3.4")

    clock["now"] += 2.0  # past the window
    guard.check_scan_rate("1.2.3.4")  # allowed again


def test_rate_limit_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "not-a-number")
    guard.check_scan_rate("1.2.3.4")  # default (20) applies, no crash


def test_rate_limit_tracked_clients_are_bounded(monkeypatch):
    """Spoofed client ids must not grow the limiter dict without limit."""
    monkeypatch.setenv("SCAN_RATE_LIMIT", "5")
    for i in range(guard._MAX_TRACKED_CLIENTS + 10):
        guard.check_scan_rate(f"10.0.{i // 256}.{i % 256}")
    assert len(guard._hits) <= guard._MAX_TRACKED_CLIENTS


# --- daily Bedrock budget ---------------------------------------------------
def test_budget_allows_then_blocks(monkeypatch):
    monkeypatch.delenv("SCANS_TABLE_NAME", raising=False)
    monkeypatch.setenv("BEDROCK_DAILY_BUDGET", "2")
    assert guard.try_consume_narrative_budget() is True
    assert guard.try_consume_narrative_budget() is True
    assert guard.try_consume_narrative_budget() is False


def test_budget_zero_disables_paid_calls(monkeypatch):
    """The absolute zero-cost setting: no Bedrock call is ever reserved."""
    monkeypatch.delenv("SCANS_TABLE_NAME", raising=False)
    monkeypatch.setenv("BEDROCK_DAILY_BUDGET", "0")
    assert guard.try_consume_narrative_budget() is False


def test_budget_falls_back_to_local_accounting_when_table_errors(monkeypatch):
    """A DynamoDB outage must not uncap spend."""
    monkeypatch.setenv("SCANS_TABLE_NAME", "fake-table")
    monkeypatch.setenv("BEDROCK_DAILY_BUDGET", "1")

    class BrokenTable:
        def update_item(self, **_kwargs):
            raise RuntimeError("dynamo unavailable")

    monkeypatch.setattr(guard, "_table_ref", lambda: BrokenTable())
    assert guard.try_consume_narrative_budget() is True   # local ceiling of 1
    assert guard.try_consume_narrative_budget() is False  # still enforced


def test_budget_respects_conditional_check_failure(monkeypatch):
    """The DynamoDB ceiling rejection maps to "use the template"."""
    monkeypatch.setenv("SCANS_TABLE_NAME", "fake-table")
    monkeypatch.setenv("BEDROCK_DAILY_BUDGET", "5")

    class ConditionalCheckFailedException(Exception):
        pass

    class FullTable:
        def update_item(self, **_kwargs):
            raise ConditionalCheckFailedException("budget spent")

    monkeypatch.setattr(guard, "_table_ref", lambda: FullTable())
    assert guard.try_consume_narrative_budget() is False


# --- narrative cache --------------------------------------------------------
def test_cache_key_is_deterministic_and_order_independent():
    a = guard.narrative_cache_key("owner/repo", 70, ["R2", "R1"])
    b = guard.narrative_cache_key("owner/repo", 70, ["R1", "R2"])
    assert a == b


def test_cache_key_changes_with_findings_and_score():
    base = guard.narrative_cache_key("owner/repo", 70, ["R1"])
    assert base != guard.narrative_cache_key("owner/repo", 71, ["R1"])
    assert base != guard.narrative_cache_key("owner/repo", 70, ["R1", "R2"])
    assert base != guard.narrative_cache_key("other/repo", 70, ["R1"])


def test_cache_is_a_noop_without_a_table(monkeypatch):
    monkeypatch.delenv("SCANS_TABLE_NAME", raising=False)
    key = guard.narrative_cache_key("owner/repo", 10, [])
    guard.narrative_cache_put(key, "text")   # must not raise
    assert guard.narrative_cache_get(key) is None


def test_cache_read_failure_is_a_miss_not_an_error(monkeypatch):
    monkeypatch.setenv("SCANS_TABLE_NAME", "fake-table")

    class BrokenTable:
        def get_item(self, **_kwargs):
            raise RuntimeError("dynamo unavailable")

    monkeypatch.setattr(guard, "_table_ref", lambda: BrokenTable())
    assert guard.narrative_cache_get("narrative#abc") is None


def test_cache_round_trip(monkeypatch):
    monkeypatch.setenv("SCANS_TABLE_NAME", "fake-table")
    store: dict[str, dict] = {}

    class FakeTable:
        def put_item(self, Item):  # noqa: N803 -- boto3 kwarg name
            store[Item["id"]] = Item

        def get_item(self, Key):  # noqa: N803 -- boto3 kwarg name
            item = store.get(Key["id"])
            return {"Item": item} if item else {}

    monkeypatch.setattr(guard, "_table_ref", lambda: FakeTable())
    key = guard.narrative_cache_key("owner/repo", 42, ["R1"])
    guard.narrative_cache_put(key, "cached narrative")
    assert guard.narrative_cache_get(key) == "cached narrative"
    assert store[key]["expires_at"] > 0  # TTL set, so the row self-deletes


# --- API integration --------------------------------------------------------
def test_retry_after_phrase_is_human_readable():
    """The detail string reaches the user verbatim (api.ts surfaces `detail`),
    so it must never read like machine output such as "retry in 3421s"."""
    from app.main import _retry_after_phrase

    assert _retry_after_phrase(5) == "5 seconds"
    assert _retry_after_phrase(0) == "1 seconds"      # never "0"
    assert _retry_after_phrase(90) == "2 minutes"     # rounds up, never "1.5"
    assert _retry_after_phrase(60) == "1 minute"      # singular
    assert _retry_after_phrase(3600) == "1 hour"
    assert _retry_after_phrase(7200) == "2 hours"


def test_rate_limited_response_is_readable(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    client = TestClient(app)
    payload = {"sourceType": "paste", "source": "s", "files": {"a.py": "x = 1"}}

    client.post("/api/scans", json=payload)
    blocked = client.post("/api/scans", json=payload)
    detail = blocked.json()["detail"]
    assert "rate limit" in detail.lower()
    assert "try again in" in detail.lower()
    # A spelled-out unit, not the raw "3421s" machine form.
    assert re.search(r"\b\d+ (seconds|minutes?|hours?)\b", detail)
    assert not re.search(r"\b\d+s\b", detail)


def test_scan_endpoint_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    client = TestClient(app)
    payload = {"sourceType": "paste", "source": "s", "files": {"a.py": "x = 1"}}

    first = client.post("/api/scans", json=payload)
    assert first.status_code == 200

    second = client.post("/api/scans", json=payload)
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


def test_rate_limit_applies_before_validation(monkeypatch):
    """Malformed payloads must burn quota too, or they are a free flood."""
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    client = TestClient(app)

    bad = {"sourceType": "paste", "source": "s"}  # paste with no files -> 422
    assert client.post("/api/scans", json=bad).status_code == 422
    assert client.post("/api/scans", json=bad).status_code == 429


def test_client_id_prefers_rightmost_forwarded_ip():
    """AWS APPENDS the real source IP to X-Forwarded-For, so the rightmost
    entry is the trustworthy one. Taking the leftmost would let a caller spoof
    a fresh identity per request and walk past the limit."""
    from app.main import _client_id

    class FakeRequest:
        def __init__(self, headers):
            self.headers = headers
            self.client = None

    req = FakeRequest({"x-forwarded-for": "9.9.9.9, 8.8.8.8, 203.0.113.7"})
    assert _client_id(req) == "203.0.113.7"


def test_spoofed_forwarded_header_cannot_reset_the_limit(monkeypatch):
    """The whole point of the rightmost choice, proven end to end.

    Simulates AWS faithfully: the proxy layer APPENDS the observed source IP, so
    a caller controls only the prefix. The spoofed leftmost value changes between
    requests while the appended real IP stays constant -- and the limit still
    bites. Reading the leftmost entry instead would hand out a fresh identity per
    request and make the limiter decorative.
    """
    monkeypatch.setenv("SCAN_RATE_LIMIT", "1")
    client = TestClient(app)
    payload = {"sourceType": "paste", "source": "s", "files": {"a.py": "x = 1"}}
    real_ip = "203.0.113.7"  # what AWS appends; the client cannot forge this

    first = client.post(
        "/api/scans", json=payload, headers={"X-Forwarded-For": f"1.1.1.1, {real_ip}"}
    )
    assert first.status_code == 200

    second = client.post(
        "/api/scans", json=payload, headers={"X-Forwarded-For": f"2.2.2.2, {real_ip}"}
    )
    assert second.status_code == 429
