"""MCP Guardian API — hardened implementation.

Routes and JSON shapes are the stable contract (see app/models.py):
    POST /api/scans          -> {"id": str}
    GET  /api/scans/{id}     -> ScanResult (camelCase) | 404
    GET  /api/scans?limit=N  -> recent scans, newest first
    GET  /api/health         -> {"ok": true, ...}

Hardening in this version: strict request validation (422 with detail),
per-scan in-memory locks (double-submits are safe), an optional concurrency
limit (MAX_CONCURRENT_SCANS env), resilient background error handling that
always lands on status=error with a useful message, ALLOWED_ORIGINS-driven
CORS, and a JSON 500 handler so unhandled errors never leak tracebacks.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models import (
    AnalysisResult,
    PolicyDecision,
    ScanRequest,
    ScanResult,
    ScanStatus,
    ServerInfo,
    SourceType,
)
from app.store import Store, get_store
from app.scanner.fetch import fetch_source
from app.scanner.analyze import analyze_bundle
from app.policy.cedar import generate_cedar_policy, split_tools
from app.agents.narrator import generate_narrative
from app import guard

logger = logging.getLogger("mcp_guardian.api")

# --- configuration ----------------------------------------------------------
_DEFAULT_ORIGINS = "http://localhost:3000"
_MAX_SOURCE_LEN = 512
_MAX_REF_LEN = 256
_MAX_PASTE_FILES = 60
_MAX_PASTE_TOTAL_BYTES = 5_000_000


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        logger.warning("invalid %s=%r; falling back to %d", name, raw, default)
        value = default
    return max(minimum, min(value, maximum))


_MAX_CONCURRENT_SCANS = _env_int("MAX_CONCURRENT_SCANS", 4, 1, 64)
_scan_slots = threading.BoundedSemaphore(_MAX_CONCURRENT_SCANS)

# Lambda mode: background threads freeze once the handler returns, so run the
# scan synchronously before responding when GUARDIAN_SYNC_SCAN=1. The frontend
# polls either way, so both modes are transparent to the UI.
_SYNC_SCAN = os.environ.get("GUARDIAN_SYNC_SCAN", "").strip() in ("1", "true", "yes")

# Per-scan locks: guarantee the same scan id is never executed twice
# (double-submit / retry races). Entries are tiny Lock objects, one per scan.
_scan_locks: dict[str, threading.Lock] = {}
_scan_locks_guard = threading.Lock()


def _scan_lock(scan_id: str) -> threading.Lock:
    with _scan_locks_guard:
        lock = _scan_locks.get(scan_id)
        if lock is None:
            lock = threading.Lock()
            _scan_locks[scan_id] = lock
        return lock


def _parse_origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


_origins = _parse_origins(os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS))


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store().init()
    logger.info("MCP Guardian starting (CORS origins: %s)", ", ".join(_origins) or "*")
    yield


app = FastAPI(title="MCP Guardian", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


# --- background scan flow ----------------------------------------------------
def _error_result(scan_id: str, request: ScanRequest, exc: BaseException, started: float) -> ScanResult:
    return ScanResult(
        id=scan_id,
        status=ScanStatus.ERROR,
        request=request,
        server=ServerInfo(name=request.source, source_type=request.source_type, source_ref=request.source),
        error=f"{type(exc).__name__}: {exc}",
        duration_ms=int((time.time() - started) * 1000),
    )


def _policy_decisions(analysis: AnalysisResult) -> list[PolicyDecision]:
    """Per-tool decisions mirroring the generated Cedar policy (same split_tools
    logic the policy generator uses), so the UI can preview enforcement."""
    safe, risky = split_tools(analysis)
    decisions: list[PolicyDecision] = []
    for tool in safe:
        decisions.append(
            PolicyDecision(tool=tool.name, effect="allow", reason="No risk signals — permit policy.")
        )
    for tool in risky:
        reason = (
            f"Flagged: {', '.join(tool.risks)}; forbid until context.approved == true."
            if tool.risks
            else "Referenced by a high/critical finding; forbid until context.approved == true."
        )
        decisions.append(PolicyDecision(tool=tool.name, effect="require-approval", reason=reason))
    return decisions


def _execute_scan(scan_id: str, request: ScanRequest, store: Store) -> None:
    started = time.time()
    try:
        store.update_status(scan_id, ScanStatus.SCANNING)
        bundle = fetch_source(request)
        analysis: AnalysisResult = analyze_bundle(bundle)
        cedar = generate_cedar_policy(bundle.server, analysis)
        narrative = generate_narrative(bundle.server, analysis)
        result = ScanResult(
            id=scan_id,
            status=ScanStatus.COMPLETE,
            request=request,
            server=bundle.server,
            risk_score=analysis.risk_score,
            risk_level=analysis.risk_level,
            findings=analysis.findings,
            tools=analysis.tools,
            policy_decisions=_policy_decisions(analysis),
            cedar_policy=cedar,
            narrative=narrative,
            duration_ms=int((time.time() - started) * 1000),
        )
        store.save(result)
    except Exception as exc:  # noqa: BLE001 — scan failures surface in the UI
        logger.exception("scan %s failed", scan_id)
        try:
            store.save(_error_result(scan_id, request, exc, started))
        except Exception:  # noqa: BLE001 — persisting the error must never crash the thread
            logger.exception("scan %s failed and its error state could not be persisted", scan_id)


def _run_scan(scan_id: str, request: ScanRequest) -> None:
    store = get_store()
    lock = _scan_lock(scan_id)
    if not lock.acquire(blocking=False):
        logger.info("scan %s already in progress; skipping duplicate run", scan_id)
        return
    try:
        current = store.get(scan_id)
        if current is not None and current.status != ScanStatus.PENDING:
            return  # already handled by another run
        with _scan_slots:
            _execute_scan(scan_id, request, store)
    except Exception as exc:  # noqa: BLE001 — last-resort net for the worker thread
        logger.exception("scan %s crashed unexpectedly", scan_id)
        try:
            store.save(_error_result(scan_id, request, exc, time.time()))
        except Exception:  # noqa: BLE001
            logger.exception("scan %s: could not persist crash state", scan_id)
    finally:
        lock.release()


# --- routes -------------------------------------------------------------------
def _validation_error(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _client_id(http_request: Request) -> str:
    """Identify the caller for rate limiting.

    Behind API Gateway and Lambda Function URLs, AWS *appends* the observed
    source IP to whatever X-Forwarded-For the client sent, so the RIGHTMOST
    entry is the one AWS vouches for. Taking the leftmost -- the usual advice
    for trusted-proxy setups -- would let a caller mint a new identity per
    request and bypass the limit entirely.
    """
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    client = http_request.client
    return client.host if client else "unknown"


def _validate_scan_request(request: ScanRequest) -> None:
    source = (request.source or "").strip()
    if not source:
        raise _validation_error("`source` must be a non-empty string")
    if len(source) > _MAX_SOURCE_LEN:
        raise _validation_error(f"`source` must be at most {_MAX_SOURCE_LEN} characters")
    if request.ref is not None and len(request.ref) > _MAX_REF_LEN:
        raise _validation_error(f"`ref` must be at most {_MAX_REF_LEN} characters")
    if request.source_type == SourceType.PASTE:
        files = request.files
        if not files:
            raise _validation_error("paste scans require `files` (path -> content)")
        if len(files) > _MAX_PASTE_FILES:
            raise _validation_error(f"paste scans accept at most {_MAX_PASTE_FILES} files")
        for path in files:
            if not path.strip():
                raise _validation_error("paste file paths must be non-empty")
        total = sum(len(content.encode("utf-8", errors="replace")) for content in files.values())
        if total > _MAX_PASTE_TOTAL_BYTES:
            raise _validation_error(f"paste payload exceeds {_MAX_PASTE_TOTAL_BYTES} bytes")


@app.get("/api/health")
def health() -> dict:
    """Liveness plus deployment diagnostics.

    Deliberately does NOT invoke Bedrock: a health check that calls a paid model
    would bill on every poll, and uptime monitors poll often. It reports the
    configuration and reachability of each dependency instead, which is what you
    actually need when a fresh deploy misbehaves.

    `store.reachable` is the useful signal on Lambda -- an IAM or table-name
    mistake shows up here as false with a reason, rather than as a 500 on the
    first scan.
    """
    store_kind = "dynamodb" if os.environ.get("SCANS_TABLE_NAME", "").strip() else "sqlite"
    store_reachable = True
    store_error: str | None = None
    try:
        get_store().list_recent(limit=1)
    except Exception as exc:  # noqa: BLE001 -- reporting the failure IS the job
        store_reachable = False
        store_error = type(exc).__name__

    return {
        "ok": True,
        "service": "mcp-guardian",
        "version": app.version,
        "store": {
            "kind": store_kind,
            "reachable": store_reachable,
            **({"error": store_error} if store_error else {}),
        },
        "narrative": {
            # Whether a paid call is even possible, without making one.
            "bedrockConfigured": bool(os.environ.get("BEDROCK_MODEL_ID")),
            "modelId": os.environ.get("BEDROCK_MODEL_ID") or "amazon.nova-lite-v1:0",
            "dailyBudget": guard._daily_narrative_budget(),
        },
        "limits": {
            "scanRateLimit": guard._rate_limit(),
            "scanRateWindowSeconds": guard._rate_window_seconds(),
            "maxConcurrentScans": _MAX_CONCURRENT_SCANS,
            "syncScan": _SYNC_SCAN,
        },
    }


def _retry_after_phrase(seconds: int) -> str:
    """Human phrasing for a Retry-After delay.

    The detail string is what the user actually reads: frontend/src/lib/api.ts
    surfaces `detail` verbatim and cannot see the status code, so "retry in
    3421s" would reach a person unchanged. Rounding up avoids telling someone
    to retry in "0 minutes".
    """
    if seconds < 60:
        return f"{max(1, seconds)} seconds"
    minutes = -(-seconds // 60)  # ceiling division
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = -(-minutes // 60)
    return f"{hours} hour{'s' if hours != 1 else ''}"


@app.post("/api/scans")
def create_scan(request: ScanRequest, http_request: Request) -> dict:
    # Rate-limit BEFORE validation, so a flood of malformed payloads is
    # throttled as well: an abusive client should burn its own quota whether
    # or not its requests parse.
    try:
        guard.check_scan_rate(_client_id(http_request))
    except guard.RateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail=(
                "Scan rate limit reached for your address — "
                f"try again in {_retry_after_phrase(exc.retry_after)}."
            ),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    _validate_scan_request(request)
    scan_id = uuid.uuid4().hex[:12]
    pending = ScanResult(
        id=scan_id,
        status=ScanStatus.PENDING,
        request=request,
        server=ServerInfo(name=request.source, source_type=request.source_type, source_ref=request.source),
    )
    try:
        get_store().save(pending)
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to persist scan %s", scan_id)
        raise HTTPException(status_code=500, detail="failed to queue scan") from exc
    if _SYNC_SCAN:
        # Lambda mode: background threads freeze once the handler returns, so
        # run the scan inline before responding. The frontend polls either way.
        _run_scan(scan_id, request)
    else:
        threading.Thread(target=_run_scan, args=(scan_id, request), daemon=True, name=f"scan-{scan_id}").start()
    return {"id": scan_id}


@app.get("/api/scans")
def list_scans(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of scans returned"),
) -> list[ScanResult]:
    return get_store().list_recent(limit=limit)


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str) -> ScanResult:
    result = get_store().get(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return result
