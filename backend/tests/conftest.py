"""Shared pytest fixtures.

The guard module (app/guard.py) keeps process-global state: an in-memory
sliding-window rate limiter and a per-day Bedrock budget counter. Without a
reset between tests that state leaks across the suite -- the default limit is 20
scans/hour and every TestClient request arrives from the same host, so the 21st
POST anywhere in the suite would start returning 429 and the failure would
surface in whichever test happened to run last. That is the kind of bug that
costs an afternoon, so isolation is enforced here rather than remembered.
"""
from __future__ import annotations

import pytest

from app import guard


@pytest.fixture(autouse=True)
def _reset_guard_state():
    """Give every test a clean rate-limit window and narrative budget."""
    guard.reset_rate_limits()
    guard.reset_narrative_budget()
    guard._reset_table_cache()
    yield
    guard.reset_rate_limits()
    guard.reset_narrative_budget()
    guard._reset_table_cache()
