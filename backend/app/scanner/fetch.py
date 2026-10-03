"""Source fetchers for MCP Guardian — hardened implementation.

Contract (do not change signatures):
    fetch_source(request: ScanRequest) -> SourceBundle

Modes
-----
* paste  : request.files (path -> text) is used as-is.
* github : request.source may be "owner/repo" or any full GitHub URL
           (https://github.com/owner/repo[.git][/tree/<ref>]), or an
           scp-style git@github.com:owner/repo.git shorthand. `request.ref`
           (branch / tag / commit SHA) wins over a /tree/<ref> in the URL.
* npm    : resolves the latest version from the npm registry, then scans
           the package's GitHub repository when one is declared. If no
           GitHub repo can be resolved, falls back (best effort) to the
           registry README plus root-level source files pulled from the
           jsDelivr CDN listing.

GitHub authentication
---------------------
Set the ``GITHUB_TOKEN`` environment variable to have all GitHub API calls
sent with ``Authorization: Bearer <token>``. Anonymous GitHub API calls are
limited to ~60/hour; an authenticated token raises that to 5,000/hour, so a
token is strongly recommended when scanning several repos in a session.

Hardening
---------
* Only code-relevant text files are fetched (.py .js .mjs .cjs .ts .tsx
  .jsx .json .md .toml .yaml .yml .txt .sh .cfg .ini). CI configs under
  .github/workflows are kept on purpose — they matter for security.
* Paths under node_modules/, dist/ and .git/ are skipped.
* Lockfiles (package-lock.json etc.) larger than 500 KB are skipped;
  ordinary files larger than 200 KB are skipped.
* Hard caps: 60 files and 2 MB of total content per scan.
* 404s and rate limits raise ValueError with actionable messages.

All outbound HTTP goes through the module-level ``_make_client`` factory so
tests can monkeypatch it and inject ``httpx.MockTransport`` (no live network
in the test suite).
"""
from __future__ import annotations

import base64
import os
import re
from typing import Optional

import httpx

from app.models import ScanRequest, ServerInfo, SourceBundle, SourceType

_GH_API = "https://api.github.com"
_NPM_REGISTRY = "https://registry.npmjs.org"
_JSD_LISTING = "https://data.jsdelivr.com/v1/packages/npm/{name}@{version}"
_JSD_CDN = "https://cdn.jsdelivr.net/npm/{name}@{version}/{path}"

_TIMEOUT = 30.0

_MAX_FILES = 60
_MAX_TOTAL_BYTES = 2_000_000
_MAX_FILE_BYTES = 200_000
_MAX_LOCKFILE_BYTES = 500_000

_RATE_LIMIT_MSG = "GitHub API rate limit — try again in an hour or paste files instead"

_TEXT_EXT = re.compile(
    r"\.(py|js|mjs|cjs|ts|tsx|jsx|json|md|txt|toml|yaml|yml|cfg|ini|sh)$", re.IGNORECASE
)
_SKIP_DIR_SEGMENTS = {"node_modules", "dist", ".git"}
_LOCKFILE_RE = re.compile(
    r"(?:^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|bun\.lock)$",
    re.IGNORECASE,
)
# github.com[:/]owner/repo... — matches https URLs, scp-style git@ URLs and
# bare "github.com/owner/repo" strings.
_GH_HOST_RE = re.compile(r"github\.com[/:](?P<path>[^\s]+)", re.IGNORECASE)


def _make_client(headers: Optional[dict[str, str]] = None) -> httpx.Client:
    """Build the httpx.Client used for all outbound requests.

    This module-level factory exists so tests can monkeypatch it and inject
    an ``httpx.MockTransport``::

        def fake_factory(headers=None):
            return httpx.Client(transport=httpx.MockTransport(handler), headers=headers)

        monkeypatch.setattr(fetch, "_make_client", fake_factory)

    Production code always calls this, so patching it redirects every request.
    """
    base = {"User-Agent": "mcp-guardian"}
    if headers:
        base.update(headers)
    return httpx.Client(timeout=_TIMEOUT, headers=base, follow_redirects=True)


def _gh_headers() -> dict[str, str]:
    """Headers for GitHub API calls; includes a Bearer token when the
    GITHUB_TOKEN env var is set (raises the API rate limit from ~60/hour
    anonymous to 5,000/hour authenticated)."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gh_get(client: httpx.Client, url: str, not_found_msg: str) -> httpx.Response:
    """GET a GitHub API URL, raising clear ValueErrors on failure."""
    resp = client.get(url)
    if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
        raise ValueError(_RATE_LIMIT_MSG)
    if resp.status_code == 404:
        raise ValueError(not_found_msg)
    if resp.status_code == 403:
        raise ValueError(
            f"GitHub API refused the request ({resp.status_code}) — the repository may be private"
        )
    if resp.status_code >= 400:
        raise ValueError(f"GitHub API error {resp.status_code} while fetching {url}")
    return resp


def _parse_github(source: str, ref: Optional[str] = None) -> tuple[str, str, str]:
    """Parse a GitHub source into (owner, repo, ref).

    Accepts "owner/repo", full URLs with or without ".git", URLs containing
    "/tree/<branch-or-tag>", scp-style "git@github.com:owner/repo.git" and
    bare "github.com/owner/repo" strings. An explicit `ref` argument wins
    over a /tree/<ref> taken from the URL; "HEAD" is the final fallback.
    """
    s = source.strip()
    if not s:
        raise ValueError("empty GitHub source")

    if "://" in s or s.startswith("git@"):
        m = _GH_HOST_RE.search(s)
        if not m:
            raise ValueError(f"not a GitHub URL: {source!r}")
        path = m.group("path")
    elif s.lower().startswith("github.com/"):
        path = s[len("github.com/"):]
    else:
        path = s

    path = path.split("#", 1)[0].split("?", 1)[0]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"expected 'owner/repo' or a GitHub URL, got: {source!r}")

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    url_ref: Optional[str] = None
    if len(parts) > 2:
        if len(parts) >= 4 and parts[2].lower() == "tree":
            url_ref = parts[3]
        else:
            raise ValueError(f"could not parse GitHub source: {source!r}")

    if not owner or not repo:
        raise ValueError(f"could not parse GitHub source: {source!r}")
    return owner, repo, ref or url_ref or "HEAD"


def _should_include(path: str, size: int) -> bool:
    """Filter tree entries down to code-relevant text files within size limits."""
    if not _TEXT_EXT.search(path):
        return False
    segments = path.lower().split("/")
    if any(seg in _SKIP_DIR_SEGMENTS for seg in segments):
        return False
    limit = _MAX_LOCKFILE_BYTES if _LOCKFILE_RE.search(path) else _MAX_FILE_BYTES
    return size <= limit


def _cap_entries(entries: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Order deterministically (shallowest paths first, then alphabetical) and
    enforce the 60-file / 2 MB caps. Files that would overflow the byte cap are
    skipped in favour of smaller ones."""
    ordered = sorted(entries, key=lambda item: (item[0].count("/"), item[0].lower()))
    chosen: list[tuple[str, int]] = []
    total = 0
    for path, size in ordered:
        if len(chosen) >= _MAX_FILES:
            break
        if total + size > _MAX_TOTAL_BYTES:
            continue
        chosen.append((path, size))
        total += size
    return chosen


def _decode_blob(payload: dict) -> Optional[str]:
    content = payload.get("content")
    if content is None:
        return None
    try:
        if payload.get("encoding") == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return str(content)
    except Exception:  # noqa: BLE001 — a single bad blob must not kill the scan
        return None


def _fetch_github(owner: str, repo: str, ref: str) -> tuple[dict, dict[str, str]]:
    """Fetch repo metadata + selected file contents. Returns (meta, files)."""
    with _make_client(_gh_headers()) as client:
        meta_resp = _gh_get(
            client,
            f"{_GH_API}/repos/{owner}/{repo}",
            f"GitHub repository not found: {owner}/{repo} — check the name or that the repo is public",
        )
        meta = meta_resp.json()
        head = ref if ref != "HEAD" else meta.get("default_branch", "main")

        tree_resp = _gh_get(
            client,
            f"{_GH_API}/repos/{owner}/{repo}/git/trees/{head}?recursive=1",
            f"GitHub ref not found: {head!r} in {owner}/{repo} — check the branch/tag/commit",
        )
        tree = tree_resp.json()

        entries = [
            (e["path"], int(e.get("size") or 0), e)
            for e in tree.get("tree", [])
            if e.get("type") == "blob"
        ]
        entries = [(p, s, e) for p, s, e in entries if _should_include(p, s)]
        selected = _cap_entries([(p, s) for p, s, _ in entries])
        by_path = {p: e for p, s, e in entries}

        files: dict[str, str] = {}
        for path, _size in selected:
            entry = by_path[path]
            blob_url = entry.get("url") or f"{_GH_API}/repos/{owner}/{repo}/git/blobs/{entry.get('sha', '')}"
            blob_resp = client.get(blob_url)
            if blob_resp.status_code != 200:
                continue
            text = _decode_blob(blob_resp.json())
            if text is not None:
                files[path] = text
    return meta, files


def _npm_repo_coords(repo_field: object) -> Optional[tuple[str, str]]:
    """Extract (owner, repo) from an npm `repository` field, if it points at GitHub."""
    url = repo_field.get("url", "") if isinstance(repo_field, dict) else str(repo_field or "")
    url = url.strip()
    if not url:
        return None
    m = re.search(
        r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url, re.IGNORECASE
    )
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"github:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", url, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return None


def _flatten_jsd_files(nodes: object, prefix: str = "") -> list[tuple[str, int]]:
    """Flatten a jsDelivr listing into (path, size) pairs.

    Handles both the nested shape (directories carry a "files" array) and the
    flat shape (every entry's "name" is a full relative path).
    """
    out: list[tuple[str, int]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name") or "")
        if not name:
            continue
        path = f"{prefix}{name}"
        children = node.get("files")
        if isinstance(children, list):
            out.extend(_flatten_jsd_files(children, prefix=f"{path}/"))
        else:
            try:
                size = int(node.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            out.append((path, size))
    return out


def _fetch_npm_fallback(pkg: str, version: str, readme: str) -> dict[str, str]:
    """Best-effort npm fallback: registry README + root-level source files
    from the jsDelivr CDN listing (no GitHub repo resolvable)."""
    files: dict[str, str] = {}
    listing_url = _JSD_LISTING.format(name=pkg, version=version)
    try:
        with _make_client() as client:
            resp = client.get(listing_url)
            if resp.status_code == 200:
                candidates = [
                    (path, size)
                    for path, size in _flatten_jsd_files(resp.json().get("files"))
                    if "/" not in path and _should_include(path, size)
                ]
                for path, _size in _cap_entries(candidates):
                    cdn_resp = client.get(_JSD_CDN.format(name=pkg, version=version, path=path))
                    if cdn_resp.status_code == 200:
                        files[path] = cdn_resp.text
    except httpx.HTTPError:  # best effort — CDN trouble must not kill the scan
        pass

    if readme and "README.md" not in files:
        files["README.md"] = readme
    return files


def _fetch_npm(pkg: str, ref: Optional[str]) -> tuple[ServerInfo, dict[str, str]]:
    with _make_client() as client:
        reg_resp = client.get(f"{_NPM_REGISTRY}/{pkg}")
    if reg_resp.status_code == 404:
        raise ValueError(f"npm package not found: {pkg}")
    if reg_resp.status_code >= 400:
        raise ValueError(f"npm registry error {reg_resp.status_code} for {pkg}")
    data = reg_resp.json()

    latest = (data.get("dist-tags") or {}).get("latest", "")
    version_meta = (data.get("versions") or {}).get(latest, {})
    if not isinstance(version_meta, dict):
        version_meta = {}
    description = (version_meta.get("description") or "")[:280] or None
    readme = str(data.get("readme") or "")

    coords = _npm_repo_coords(version_meta.get("repository") or data.get("repository"))
    if coords:
        owner, repo = coords
        meta, files = _fetch_github(owner, repo, ref or "HEAD")
        if not description:
            description = (meta.get("description") or "")[:280] or None
    else:
        if not latest:
            raise ValueError(
                f"npm package '{pkg}' has no published version and no GitHub repository — paste the files instead"
            )
        files = _fetch_npm_fallback(pkg, latest, readme)
        if not files:
            raise ValueError(
                f"could not fetch source for npm package '{pkg}' — no GitHub repository and nothing usable on the CDN; paste the files instead"
            )

    server = ServerInfo(
        name=pkg,
        source_type=SourceType.NPM,
        source_ref=f"npm:{pkg}",
        version=latest or None,
        description=description,
    )
    return server, files


def fetch_source(request: ScanRequest) -> SourceBundle:
    """Fetch a SourceBundle for the given ScanRequest (see module docstring)."""
    if request.source_type == SourceType.PASTE:
        files = dict(request.files or {})
        name = request.source or "pasted-server"
        desc = files.get("README.md", "")[:280] if files else None
        return SourceBundle(
            server=ServerInfo(
                name=name, source_type=SourceType.PASTE, source_ref=request.source, description=desc
            ),
            files=files,
        )

    if request.source_type == SourceType.GITHUB:
        owner, repo, ref = _parse_github(request.source, request.ref)
        meta, files = _fetch_github(owner, repo, ref)
        return SourceBundle(
            server=ServerInfo(
                name=repo,
                source_type=SourceType.GITHUB,
                source_ref=f"{owner}/{repo}",
                description=(meta.get("description") or "")[:280] or None,
                version=ref if ref != "HEAD" else None,
            ),
            files=files,
        )

    if request.source_type == SourceType.NPM:
        pkg = request.source.strip().removeprefix("npm:").strip()
        if not pkg:
            raise ValueError("npm scan requires a package name")
        server, files = _fetch_npm(pkg, request.ref)
        return SourceBundle(server=server, files=files)

    raise ValueError(f"unsupported source type: {request.source_type}")
