"""Tests for app.scanner.fetch — all network traffic goes through
httpx.MockTransport, injected by monkeypatching the module-level
``_make_client`` factory. No live network is used.
"""
from __future__ import annotations

import base64
import json
from typing import Callable, Optional

import httpx
import pytest

from app.models import ScanRequest, SourceType
from app.scanner import fetch as fetch_mod
from app.scanner.fetch import fetch_source

RATE_LIMIT_MSG = (
    "GitHub API rate limit — try again in an hour or paste files instead"
)


# ---------------------------------------------------------------- helpers

def _resp(status: int = 200, body=None, headers: Optional[dict] = None) -> httpx.Response:
    if isinstance(body, (dict, list)):
        return httpx.Response(status, headers=headers or {}, json=body)
    return httpx.Response(status, headers=headers or {}, text=body if body is not None else "")


def _blob(content: str) -> dict:
    return {
        "encoding": "base64",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


def _tree(entries: list[tuple[str, int]], repo: str = "owner/repo") -> dict:
    return {
        "sha": "treesha",
        "truncated": False,
        "tree": [
            {
                "path": path,
                "type": "blob",
                "size": size,
                "url": f"https://api.github.com/repos/{repo}/git/blobs/{i}",
            }
            for i, (path, size) in enumerate(entries)
        ],
    }


def _gh_handler(
    *,
    meta: Optional[dict] = None,
    trees: dict,
    blobs: Optional[dict[int, str]] = None,
    seen: Optional[dict] = None,
    meta_status: int = 200,
    tree_status: int = 200,
    meta_headers: Optional[dict] = None,
):
    """Build a MockTransport handler faking api.github.com for owner/repo."""
    blob_content = blobs or {}
    seen = seen if seen is not None else {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.setdefault("urls", []).append(str(request.url))
        seen.setdefault("auth", request.headers.get("authorization"))
        if path == "/repos/owner/repo":
            seen["meta"] = True
            return _resp(meta_status, meta if meta_status == 200 else {"message": "nope"}, meta_headers)
        if path.startswith("/repos/owner/repo/git/trees/"):
            seen["tree_ref"] = path.rsplit("/", 1)[1]
            return _resp(tree_status, trees if tree_status == 200 else {"message": "nope"})
        if path.startswith("/repos/owner/repo/git/blobs/"):
            idx = int(path.rsplit("/", 1)[1])
            content = blob_content.get(idx, f"content of blob {idx}")
            return _resp(200, _blob(content))
        raise AssertionError(f"unexpected GitHub URL: {request.url}")

    return handler


@pytest.fixture
def install_handler(monkeypatch) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    """Monkeypatch fetch._make_client to return a client backed by httpx.MockTransport."""

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        transport = httpx.MockTransport(handler)

        def factory(headers: Optional[dict[str, str]] = None) -> httpx.Client:
            return httpx.Client(transport=transport, headers=headers)

        monkeypatch.setattr(fetch_mod, "_make_client", factory)

    return install


def _github_request(source: str, ref: Optional[str] = None) -> ScanRequest:
    return ScanRequest(source_type=SourceType.GITHUB, source=source, ref=ref)


# ---------------------------------------------------------------- paste

def test_paste_mode_passes_files_through(install_handler):
    install_handler(lambda req: pytest.fail("paste mode must not touch the network"))

    files = {"server.py": "print('hi')", "README.md": "# My MCP server"}
    bundle = fetch_source(ScanRequest(source_type=SourceType.PASTE, source="my-server", files=files))

    assert bundle.files == files
    assert bundle.server.source_type is SourceType.PASTE
    assert bundle.server.name == "my-server"
    assert bundle.server.source_ref == "my-server"
    assert bundle.server.description == "# My MCP server"


def test_paste_mode_without_readme_or_files(install_handler):
    install_handler(lambda req: pytest.fail("paste mode must not touch the network"))

    bundle = fetch_source(ScanRequest(source_type=SourceType.PASTE, source="x", files={"a.py": "x=1"}))
    assert bundle.server.description == ""  # baseline behavior: empty when no README.md
    assert bundle.files == {"a.py": "x=1"}


# ---------------------------------------------------------------- github parsing

@pytest.mark.parametrize(
    "source,expected_ref",
    [
        ("owner/repo", "main"),  # ref resolved from default_branch
        ("https://github.com/owner/repo", "main"),
        ("https://github.com/owner/repo.git", "main"),
        ("https://www.github.com/owner/repo", "main"),
        ("https://github.com/owner/repo/tree/develop", "develop"),
        ("https://github.com/owner/repo.git/tree/v1.2.3", "v1.2.3"),
        ("git@github.com:owner/repo.git", "main"),
        ("github.com/owner/repo", "main"),
        ("owner/repo/tree/feature/x", "feature"),  # first segment after /tree/
    ],
)
def test_github_source_parsing_variants(install_handler, source, expected_ref):
    seen: dict = {}
    trees = _tree([("server.py", 20)], repo="owner/repo")
    blobs = {0: "x=1"}
    install_handler(_gh_handler(meta={"default_branch": "main", "description": "d"}, trees=trees, blobs=blobs, seen=seen))

    bundle = fetch_source(_github_request(source))
    assert seen["tree_ref"] == expected_ref
    assert bundle.server.source_ref == "owner/repo"
    assert bundle.server.name == "repo"


def test_github_explicit_ref_wins_over_tree_url(install_handler):
    seen: dict = {}
    install_handler(
        _gh_handler(
            meta={"default_branch": "main"},
            trees=_tree([("a.py", 5)]),
            seen=seen,
        )
    )
    fetch_source(_github_request("https://github.com/owner/repo/tree/develop", ref="release-2"))
    assert seen["tree_ref"] == "release-2"


@pytest.mark.parametrize(
    "bad",
    ["justarepo", "https://gitlab.com/owner/repo", "owner/repo/extra/stuff", "", "https://example.com/x"],
)
def test_github_bad_sources_raise_valueerror(install_handler, bad):
    install_handler(lambda req: pytest.fail("must not hit the network for unparseable sources"))
    with pytest.raises(ValueError):
        fetch_source(_github_request(bad))


# ---------------------------------------------------------------- github filtering + caps

def test_github_file_filtering(install_handler):
    entries = [
        ("server.py", 100),                      # keep
        ("src/tools.ts", 100),                   # keep
        (".github/workflows/ci.yml", 50),        # keep — CI configs matter
        ("README.md", 200),                      # keep
        ("notes.txt", 10),                       # keep
        ("settings.ini", 10),                    # keep
        ("package-lock.json", 400_000),          # keep — lockfile under 500KB
        ("node_modules/pkg/index.js", 10),       # skip: node_modules
        ("dist/config.json", 10),                # skip: dist
        (".git/hooks/post-checkout.py", 10),     # skip: .git
        ("logo.png", 10),                        # skip: extension
        ("sub/package-lock.json", 600_000),      # skip: lockfile > 500KB
        ("huge.py", 250_000),                    # skip: > 200KB
        ("archive.tar.gz", 10),                  # skip: extension
    ]
    seen: dict = {}
    install_handler(
        _gh_handler(
            meta={"default_branch": "main", "description": "d"},
            trees=_tree(entries),
            blobs={i: f"content {i}" for i in range(len(entries))},
            seen=seen,
        )
    )
    bundle = fetch_source(_github_request("owner/repo"))

    assert set(bundle.files) == {
        "server.py",
        "src/tools.ts",
        ".github/workflows/ci.yml",
        "README.md",
        "notes.txt",
        "settings.ini",
        "package-lock.json",
    }
    assert bundle.files["package-lock.json"] == "content 6"
    assert bundle.server.description == "d"


def test_github_caps_at_60_files(install_handler):
    entries = [(f"f{i:03}.py", 1_000) for i in range(70)]
    install_handler(_gh_handler(meta={"default_branch": "main"}, trees=_tree(entries)))
    bundle = fetch_source(_github_request("owner/repo"))
    assert len(bundle.files) == 60


def test_github_caps_total_bytes_at_2mb(install_handler):
    # 30 files x 100KB = 3MB > 2MB cap -> only 20 fit.
    entries = [(f"m{i:03}.py", 100_000) for i in range(30)]
    install_handler(_gh_handler(meta={"default_branch": "main"}, trees=_tree(entries)))
    bundle = fetch_source(_github_request("owner/repo"))
    assert len(bundle.files) == 20


def test_github_blob_fetch_failure_is_skipped(install_handler):
    entries = [("ok.py", 10), ("broken.py", 10)]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/owner/repo":
            return _resp(200, {"default_branch": "main"})
        if path.startswith("/repos/owner/repo/git/trees/"):
            return _resp(200, _tree(entries))
        if path.endswith("/git/blobs/1"):
            return _resp(500, {"message": "boom"})
        if path.endswith("/git/blobs/0"):
            return _resp(200, _blob("fine = True"))
        raise AssertionError(f"unexpected URL {request.url}")

    install_handler(handler)
    bundle = fetch_source(_github_request("owner/repo"))
    assert bundle.files == {"ok.py": "fine = True"}


# ---------------------------------------------------------------- github errors

def test_github_rate_limit_message(install_handler):
    seen: dict = {}
    install_handler(
        _gh_handler(
            meta={"default_branch": "main"},
            trees=_tree([("a.py", 1)]),
            seen=seen,
            meta_status=403,
            meta_headers={"x-ratelimit-remaining": "0"},
        )
    )
    with pytest.raises(ValueError) as excinfo:
        fetch_source(_github_request("owner/repo"))
    assert str(excinfo.value) == RATE_LIMIT_MSG


def test_github_404_message(install_handler):
    seen: dict = {}
    install_handler(
        _gh_handler(
            meta={"default_branch": "main"},
            trees=_tree([("a.py", 1)]),
            seen=seen,
            meta_status=404,
        )
    )
    with pytest.raises(ValueError) as excinfo:
        fetch_source(_github_request("owner/repo"))
    assert "not found" in str(excinfo.value)
    assert "owner/repo" in str(excinfo.value)


def test_github_unknown_ref_404_message(install_handler):
    seen: dict = {}
    install_handler(
        _gh_handler(
            meta={"default_branch": "main"},
            trees=_tree([("a.py", 1)]),
            seen=seen,
            tree_status=404,
        )
    )
    with pytest.raises(ValueError) as excinfo:
        fetch_source(_github_request("owner/repo", ref="nope"))
    assert "nope" in str(excinfo.value)


def test_github_token_sent_as_bearer(install_handler, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok-123")
    seen: dict = {}
    install_handler(
        _gh_handler(meta={"default_branch": "main"}, trees=_tree([("a.py", 5)]), seen=seen)
    )
    fetch_source(_github_request("owner/repo"))
    assert seen["auth"] == "Bearer tok-123"


def test_github_no_token_by_default(install_handler, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen: dict = {}
    install_handler(
        _gh_handler(meta={"default_branch": "main"}, trees=_tree([("a.py", 5)]), seen=seen)
    )
    fetch_source(_github_request("owner/repo"))
    assert seen["auth"] is None


# ---------------------------------------------------------------- npm -> github

def test_npm_resolves_github_repo(install_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        if host == "registry.npmjs.org":
            return _resp(
                200,
                {
                    "dist-tags": {"latest": "1.2.3"},
                    "versions": {
                        "1.2.3": {
                            "description": "npm pkg with repo",
                            "repository": {"type": "git", "url": "git+https://github.com/owner/repo.git"},
                        }
                    },
                },
            )
        if host == "api.github.com" and path == "/repos/owner/repo":
            return _resp(200, {"default_branch": "main", "description": "gh desc"})
        if host == "api.github.com" and path.startswith("/repos/owner/repo/git/trees/"):
            return _resp(200, _tree([("index.js", 30)]))
        if host == "api.github.com" and path.startswith("/repos/owner/repo/git/blobs/"):
            return _resp(200, _blob("console.log('mcp')"))
        raise AssertionError(f"unexpected URL {request.url}")

    install_handler(handler)
    bundle = fetch_source(ScanRequest(source_type=SourceType.NPM, source="some-pkg"))

    assert bundle.server.source_type is SourceType.NPM
    assert bundle.server.name == "some-pkg"
    assert bundle.server.source_ref == "npm:some-pkg"
    assert bundle.server.version == "1.2.3"
    assert bundle.server.description == "npm pkg with repo"
    assert bundle.files == {"index.js": "console.log('mcp')"}


def test_npm_package_not_found(install_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "registry.npmjs.org"
        return _resp(404, {"error": "Not found"})

    install_handler(handler)
    with pytest.raises(ValueError) as excinfo:
        fetch_source(ScanRequest(source_type=SourceType.NPM, source="nope-pkg"))
    assert "nope-pkg" in str(excinfo.value)


# ---------------------------------------------------------------- npm fallback (jsDelivr)

def test_npm_fallback_fetches_readme_and_root_files(install_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        if host == "registry.npmjs.org":
            # repository points at a non-GitHub host -> no GitHub repo resolvable
            return _resp(
                200,
                {
                    "dist-tags": {"latest": "2.0.1"},
                    "readme": "# registry readme",
                    "versions": {
                        "2.0.1": {
                            "description": "fallback pkg",
                            "repository": {"type": "git", "url": "git+https://gitlab.com/a/b.git"},
                        }
                    },
                },
            )
        if host == "data.jsdelivr.com" and path == "/v1/packages/npm/fallback-pkg@2.0.1":
            # nested listing: lib/deep.js must be ignored (top-level only)
            return _resp(
                200,
                {
                    "files": [
                        {"name": "index.js", "size": 50},
                        {"name": "README.md", "size": 30},
                        {"name": "logo.png", "size": 10},
                        {"name": "lib", "files": [{"name": "deep.js", "size": 10}]},
                        {"name": "huge.py", "size": 900_000},
                    ]
                },
            )
        if host == "cdn.jsdelivr.net" and path == "/npm/fallback-pkg@2.0.1/index.js":
            return _resp(200, "console.log('fallback')")
        if host == "cdn.jsdelivr.net" and path == "/npm/fallback-pkg@2.0.1/README.md":
            return _resp(200, "# cdn readme")
        raise AssertionError(f"unexpected URL {request.url}")

    install_handler(handler)
    bundle = fetch_source(ScanRequest(source_type=SourceType.NPM, source="fallback-pkg"))

    assert bundle.server.version == "2.0.1"
    assert bundle.server.source_ref == "npm:fallback-pkg"
    assert bundle.files == {"index.js": "console.log('fallback')", "README.md": "# cdn readme"}


def test_npm_fallback_uses_registry_readme_when_cdn_fails(install_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "registry.npmjs.org":
            return _resp(
                200,
                {
                    "dist-tags": {"latest": "0.1.0"},
                    "readme": "# from registry",
                    "versions": {"0.1.0": {"description": "x", "repository": "https://gitlab.com/a/b"}},
                },
            )
        if host == "data.jsdelivr.com":
            return _resp(404, {"message": "listing unavailable"})
        raise AssertionError(f"unexpected URL {request.url}")

    install_handler(handler)
    bundle = fetch_source(ScanRequest(source_type=SourceType.NPM, source="only-readme"))
    assert bundle.files == {"README.md": "# from registry"}
    assert bundle.server.version == "0.1.0"


def test_npm_fallback_total_failure_raises(install_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "registry.npmjs.org":
            return _resp(200, {"dist-tags": {"latest": "0.1.0"}, "versions": {"0.1.0": {}}})
        if host == "data.jsdelivr.com":
            return _resp(404, {"message": "nope"})
        raise AssertionError(f"unexpected URL {request.url}")

    install_handler(handler)
    with pytest.raises(ValueError) as excinfo:
        fetch_source(ScanRequest(source_type=SourceType.NPM, source="ghost-pkg"))
    assert "ghost-pkg" in str(excinfo.value)
