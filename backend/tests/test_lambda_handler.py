"""Tests for the Lambda entrypoint (app/lambda_handler.py).

Why this file exists: every other test drives the app through
``fastapi.testclient.TestClient``, which imports ``app.main`` and never touches
``app.lambda_handler``. That left the deployed entrypoint completely untested --
and it broke exactly there: ``handler = Mangum(...)`` runs at MODULE IMPORT
time, so when Mangum 0.22 renamed ``api_gateway_base_paths`` (plural, list) to
``api_gateway_base_path`` (singular, str), the deploy died on a cold start with
``TypeError: unexpected keyword argument`` while all 122 local tests stayed
green.

Importing this module is therefore the assertion: a signature mismatch between
the code and the vendored Mangum fails collection here instead of after a
deploy. The event-shaped tests then confirm the adapter actually routes both
payload formats the stack exposes (Lambda Function URL v2 and API Gateway REST
v1), which is what the no-base-path decision in lambda_handler.py rests on.
"""
from __future__ import annotations

import importlib
import json

import pytest

import app.store as store_mod


@pytest.fixture()
def lambda_module(tmp_path, monkeypatch):
    """Import the entrypoint with a throwaway SQLite path.

    ``app.lambda_handler`` eagerly calls ``get_store().init()`` at import time,
    which would otherwise create ./guardian.db in the repo root as a test side
    effect. The store singleton is reset so the patched path is actually used.
    """
    monkeypatch.setenv("GUARDIAN_DB_PATH", str(tmp_path / "test-guardian.db"))
    monkeypatch.delenv("SCANS_TABLE_NAME", raising=False)
    monkeypatch.setattr(store_mod, "_store", None)

    module = importlib.import_module("app.lambda_handler")
    # Re-import under the patched env even if a previous test already loaded it.
    module = importlib.reload(module)
    yield module

    monkeypatch.setattr(store_mod, "_store", None)


def _function_url_event(method: str = "GET", path: str = "/api/health") -> dict:
    """A Lambda Function URL request (payload format 2.0)."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "abc123.lambda-url.us-east-1.on.aws", "accept": "*/*"},
        "requestContext": {
            "accountId": "anonymous",
            "apiId": "abc123",
            "domainName": "abc123.lambda-url.us-east-1.on.aws",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.10",
                "userAgent": "pytest",
            },
            "requestId": "test-request-id",
            "routeKey": "$default",
            "stage": "$default",
            "time": "19/Sep/2026:10:00:00 +0000",
            "timeEpoch": 1789811323000,
        },
        "isBase64Encoded": False,
    }


def _rest_api_event(method: str = "GET", path: str = "/api/health") -> dict:
    """An API Gateway REST proxy request (payload format 1.0).

    Note the two different paths: ``event["path"]`` arrives with the stage
    ALREADY stripped, while ``requestContext.path`` still carries "/Prod". That
    asymmetry is the reason no base-path argument is needed.
    """
    return {
        "resource": "/{proxy+}",
        "path": path,
        "httpMethod": method,
        "headers": {"Host": "bpi1wlgj58.execute-api.us-east-1.amazonaws.com"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "pathParameters": {"proxy": path.lstrip("/")},
        "requestContext": {
            "resourcePath": "/{proxy+}",
            "httpMethod": method,
            "path": f"/Prod{path}",
            "stage": "Prod",
            "requestId": "test-request-id",
            "identity": {"sourceIp": "203.0.113.10", "userAgent": "pytest"},
            "protocol": "HTTP/1.1",
        },
        "body": None,
        "isBase64Encoded": False,
    }


def test_handler_is_constructed_at_import(lambda_module):
    """The regression guard: importing the module must not raise."""
    assert callable(lambda_module.handler)


def test_function_url_event_reaches_the_app(lambda_module):
    """The recommended endpoint (Function URL, payload 2.0) routes correctly."""
    response = lambda_module.handler(_function_url_event(), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["ok"] is True
    assert body["service"] == "mcp-guardian"


def test_rest_api_event_reaches_the_app(lambda_module):
    """The API Gateway alternative (payload 1.0) routes without a base path."""
    response = lambda_module.handler(_rest_api_event(), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["ok"] is True


def test_unknown_route_still_returns_json_404(lambda_module):
    """A miss must surface as the app's 404, not a runtime crash (502)."""
    response = lambda_module.handler(_function_url_event(path="/api/nope"), None)

    assert response["statusCode"] == 404


def test_store_is_initialised_eagerly(lambda_module):
    """Lambda delivers no ASGI lifespan events, so init must happen at import."""
    # A reachable store proves init() ran: the health payload reports it.
    response = lambda_module.handler(_function_url_event(), None)
    store = json.loads(response["body"])["store"]

    assert store["kind"] == "sqlite"
    assert store["reachable"] is True
