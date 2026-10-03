"""AWS Lambda entrypoint for the MCP Guardian API.

Local development does NOT use this module — uvicorn runs ``app.main:app``
directly (see the root Makefile). On AWS Lambda, Mangum translates API Gateway
proxy events to ASGI (pinned in backend/requirements.txt).

Deployment notes:
  * The store is initialised eagerly because API Gateway invocations do not
    deliver ASGI lifespan events; ``SQLiteStore.init()`` is idempotent
    (CREATE TABLE IF NOT EXISTS) so re-running it on warm starts is harmless.
  * ``lifespan="off"`` keeps Mangum from managing lifespan, matching the eager
    init above and avoiding per-invocation startup overhead.
  * No base-path argument is passed. Mangum's default ("/") is correct for the
    Lambda Function URL (the recommended endpoint, which has no stage prefix)
    AND for API Gateway REST proxy events, whose ``event["path"]`` already has
    the stage stripped. Passing one would also tie this module to a single
    Mangum signature: 0.22 renamed ``api_gateway_base_paths`` (plural, list) to
    ``api_gateway_base_path`` (singular, str), which broke a deploy with
    ``TypeError: unexpected keyword argument`` while every local test passed --
    uvicorn imports ``app.main``, never this module.
"""

from mangum import Mangum

from app.main import app
from app.store import get_store

try:  # never fail a cold start on store init — routes degrade gracefully
    get_store().init()
except Exception:  # noqa: BLE001 — scanning still works; persistence may not
    pass

handler = Mangum(app, lifespan="off")
