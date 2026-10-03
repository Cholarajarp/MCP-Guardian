"""Static analysis engine — MCP Guardian rules engine.

Owned by the analysis-engine agent (rule registry + scoring + tests).
Contract (do not change signatures):
    analyze_bundle(bundle: SourceBundle) -> AnalysisResult

Architecture: a registry of declarative Rule entries (id, title, severity,
description template, remediation, detector). File-scoped detectors scan raw
source text; tool-scoped rules (prompt injection in descriptions, destructive
tools, shell passthrough tools, description/content mismatch) run over the
extracted tool records, which carry decorator annotations + function body.
Scoring is severity-weighted and capped at 100 (critical 30, high 18,
medium 8, low 3) with risk levels at thresholds 70/40/15.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

from app.models import AnalysisResult, Finding, RiskLevel, Severity, SourceBundle, ToolInfo

# ---------------------------------------------------------------- constants

MAX_PER_RULE_PER_FILE = 3

SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 30,
    Severity.HIGH: 18,
    Severity.MEDIUM: 8,
    Severity.LOW: 3,
    Severity.INFO: 0,
}
_SEV_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}

_CODE_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")

# ---------------------------------------------------------------- helpers


def _is_code(path: str) -> bool:
    p = path.replace("\\", "/")
    return "node_modules/" not in p and p.endswith(_CODE_EXT)


def _is_shell_script(path: str) -> bool:
    return path.replace("\\", "/").endswith(".sh")


def _is_requirements(path: str) -> bool:
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name.startswith("requirements") and name.endswith(".txt")


def _is_package_json(path: str) -> bool:
    p = path.replace("\\", "/")
    return p.endswith("package.json") and "node_modules/" not in p


def _line_of(content: str, idx: int) -> int:
    return content.count("\n", 0, idx) + 1


def _line_text(content: str, idx: int, limit: int = 140) -> str:
    start = content.rfind("\n", 0, idx) + 1
    end = content.find("\n", idx)
    if end == -1:
        end = len(content)
    return content[start:end].strip()[:limit]


def _m(content: str, idx: int, detail: str, severity: Optional[Severity] = None, evidence: str = "") -> dict:
    """Build a detector match record."""
    return {
        "line": _line_of(content, idx),
        "detail": detail,
        "evidence": evidence or _line_text(content, idx),
        "severity": severity,
    }


def _read_block(s: str, open_idx: int) -> tuple[str, int]:
    """Return (inner_text, index_after_closing) for the bracketed block."""
    opener = s[open_idx]
    closer = {"(": ")", "[": "]", "{": "}"}[opener]
    depth, i, n = 0, open_idx, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c
            i += 1
            while i < n and s[i] != q:
                if s[i] == "\\":
                    i += 1
                i += 1
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i], i + 1
        i += 1
    return s[open_idx + 1:], n


# ------------------------------------------------- file-scoped rule detectors


def _det_eval_exec(path: str, content: str) -> list[dict]:
    out = []
    for m in re.finditer(r"(?<![\w.])(?:eval|exec)\s*\(", content):
        out.append(_m(content, m.start(), "eval()/exec() executes a dynamically constructed string."))
    return out


def _det_shell_exec(path: str, content: str) -> list[dict]:
    out = []
    pat = re.compile(
        r"(?<![\w.])(?:os\.(?:system|popen)\s*\(|subprocess\.(?:run|call|check_call|check_output|Popen|getoutput)\s*\(|child_process|execSync\s*\(|spawnSync\s*\()"
    )
    for m in pat.finditer(content):
        ctx = content[m.start():m.start() + 300]
        if re.search(r"shell\s*=\s*True", ctx):
            out.append(_m(content, m.start(), "Shell invocation with shell=True runs a raw command string."))
        elif "os.system" in m.group(0) or "popen" in m.group(0):
            out.append(_m(content, m.start(), "os.system/os.popen runs a shell command."))
        else:
            out.append(
                _m(content, m.start(), "subprocess call executes an external program.", severity=Severity.MEDIUM)
            )
    return out


def _det_encoded_exec(path: str, content: str) -> list[dict]:
    out = []
    for m in re.finditer(r"(?:base64\.b64decode|b64decode|base64\.decodebytes|codecs\.decode)\s*\(", content):
        window = content[max(0, m.start() - 300):m.start() + 400]
        nxt = re.search(r"(?<![\w.])(?:eval|exec)\s*\(|__import__|os\.system|subprocess\.|Popen|marshal\.loads|pickle\.loads", window)
        if nxt:
            out.append(_m(content, m.start(), "Decoded (base64) data is fed into dynamic execution."))
    return out


def _det_dynamic_import(path: str, content: str) -> list[dict]:
    out = []
    for m in re.finditer(r"(?<![\w.])(?:__import__|importlib\.import_module|importlib\.reload)\s*\(\s*(?![\"'])", content):
        out.append(_m(content, m.start(), "Module imported from a computed/variable name instead of a literal."))
    return out


def _det_obfuscation(path: str, content: str) -> list[dict]:
    out = []
    for m in re.finditer(r"[\"']([A-Za-z0-9+/=]{120,}|[A-Fa-f0-9]{120,})[\"']", content):
        blob = m.group(1)
        has_digit = any(c.isdigit() for c in blob)
        mixed = any(c.isupper() for c in blob) and any(c.islower() for c in blob)
        if not (has_digit or mixed or "+" in blob or "/" in blob or "=" in blob):
            continue
        out.append(_m(content, m.start(), "Large hex/base64 literal hides its payload from review.", evidence=blob[:100] + "..."))
    return out


_EXFIL_HOSTS = (
    "webhook.site", "ngrok", "pastebin.com", "requestbin", "pipedream.net",
    "hookb.in", "postb.in", "interact.sh", "oast.", "requestcatcher",
    "burpcollaborator", "discord.com/api/webhooks", "hooks.slack.com/services",
)
_EGRESS_ALLOWLIST = (
    "api.github.com", "registry.npmjs.org", "pypi.org", "api.openai.com",
    "api.anthropic.com", "generativelanguage.googleapis.com", "localhost",
    "127.0.0.1", "0.0.0.0", "example.com", "bedrock-runtime",
)
_POST_CALL = re.compile(
    r"(?<![\w.])(?:requests|httpx|session|client|http|axios)\s*\.\s*post\s*\(|urlopen\s*\(|(?<![\w.])fetch\s*\("
)
_URL = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")


def _det_net_exfil(path: str, content: str) -> list[dict]:
    out = []
    # 1) code that sends data to a known exfil endpoint
    for m in _URL.finditer(content):
        url = m.group(0).lower()
        if not any(h in url for h in _EXFIL_HOSTS):
            continue
        ctx = content[m.start():m.start() + 300]
        if re.search(r"(?i)\b(post|send|upload|fetch|urlopen|request|httpx|requests|curl|wget)\b", ctx):
            out.append(_m(content, m.start(), f"Code contacts a known exfiltration endpoint: {url.split('/')[2]}."))
    # 2) any POST of env/credentials to a non-allowlisted host
    for m in _POST_CALL.finditer(content):
        window = content[m.start():m.start() + 600]
        um = _URL.search(window)
        if not um:
            continue
        url = um.group(0).lower()
        if any(a in url for a in _EGRESS_ALLOWLIST):
            continue
        if re.search(r"(?i)os\.environ|process\.env|api[_-]?key|apikey|secret|password|credential|\btoken\b|AKIA|PRIVATE KEY", window):
            out.append(_m(content, m.start(), f"POST sends environment/credential data to a non-allowlisted host ({url.split('/')[2]})."))
    return out


def _det_env_harvest(path: str, content: str) -> list[dict]:
    out = []
    pats = [
        r"os\.environ\.copy\s*\(",
        r"\bdict\s*\(\s*os\.environ",
        r"json\.dumps\s*\(\s*os\.environ",
        r"\bstr\s*\(\s*os\.environ\s*\)",
        r"\blist\s*\(\s*os\.environ",
        r"os\.environ\.items\s*\(\s*\)",
        r"\breturn\s+os\.environ\b",
        r"JSON\.stringify\s*\(\s*process\.env\s*\)",
        r"\{\s*\.\.\.process\.env\s*\}",
        r"\breturn\s+process\.env\b",
        r"Object\.(?:entries|keys|values)\s*\(\s*process\.env\s*\)",
    ]
    for pat in pats:
        for m in re.finditer(pat, content):
            out.append(_m(content, m.start(), "Entire process environment is collected (all variables, values included)."))
    return out


_SECRET_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(
        r"(?i)(?<![A-Za-z])(api[_-]?key|apikey|secret(?:[_-]?key|[_-]?token)?|access[_-]?(?:key|token)|"
        r"auth[_-]?token|password|passwd|client[_-]?secret|private[_-]?token)[\"']?\s*[:=]\s*[\"']([^\"'\n]{8,})[\"']"
    ),
]
_SECRET_PLACEHOLDER = re.compile(
    r"(?i)(your[-_ ]|sample[-_ ]|placeholder|insert |xxxx|<[^>]+>|\{\{|\$\{|changeme|redacted|dummy)"
)


def _det_hardcoded_secret(path: str, content: str) -> list[dict]:
    out = []
    for lineno, line in enumerate(content.splitlines(), 1):
        if "os.environ" in line or "getenv" in line or "process.env" in line:
            continue
        for pat in _SECRET_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            if pat.pattern.startswith("(?i)(?<![A-Za-z])(api") and _SECRET_PLACEHOLDER.search(m.group(len(m.groups()))):
                continue
            out.append({"line": lineno, "detail": "Credential material is committed in source.", "evidence": line.strip()[:140], "severity": None})
            break
    return out


def _det_dotenv(path: str, content: str) -> list[dict]:
    out = []
    pats = [
        r"dotenv_values\s*\(",
        r"[\"']\.env[\"']",
        r"open\s*\(\s*[\"'][^\"']*\.env\b[^\"']*[\"']",
        r"Path\s*\(\s*[\"'][^\"']*\.env\b[^\"']*[\"']\s*\)",
        r"readFileSync\s*\(\s*[\"'][^\"']*\.env\b",
    ]
    for pat in pats:
        for m in re.finditer(pat, content):
            out.append(_m(content, m.start(), ".env file contents are read at runtime by server code."))
    return out


def _det_fs_write(path: str, content: str) -> list[dict]:
    out = []
    pats = [
        r"open\s*\(\s*[\"'](?:/(?:etc|var|usr|bin|sbin|root|home|proc|sys)|~)[^\"']*[\"']\s*,\s*[\"'][wa]",
        r"open\s*\(\s*[\"'][^\"']*\.\.[/\\][^\"']*[\"']\s*,\s*[\"'][wa]",
        r"open\s*\(\s*[\"'][A-Za-z]:[\\/][^\"']*[\"']\s*,\s*[\"'][wa]",
        r"os\.(?:remove|unlink|rmdir|makedirs?)\s*\(\s*[\"'](?:/|~|[A-Za-z]:[\\/])",
        r"shutil\.rmtree\s*\(\s*[\"'](?:/|~|[A-Za-z]:[\\/])",
        r"Path\s*\(\s*[\"'][^\"']*\.\.[^\"']*[\"']\s*\)\.(?:write_text|write_bytes|unlink|rmtree)",
        r"fs\.(?:writeFile|appendFile|writeFileSync|appendFileSync|unlink|rm|rmdir)\s*\(\s*[\"'](?:/|~|\.\.|[A-Za-z]:\\)",
    ]
    for pat in pats:
        for m in re.finditer(pat, content):
            out.append(_m(content, m.start(), "Write/delete targets an absolute path or escapes via '..' traversal."))
    return out


_SENSITIVE_PATH = re.compile(
    r"(?i)[\"'`][^\"'`]*(?:\.ssh[/\\]|id_rsa|id_ed25519|\.aws[/\\]credentials|User Data[/\\]|Firefox[/\\]Profiles|"
    r"\.mozilla|cookies\.sqlite|Login Data|wallet\.dat|metamask|\.bitcoin|\.ethereum|\.netrc|\.git-credentials|"
    r"\.kube[/\\]config|\.docker[/\\]config)[^\"'`]*[\"'`]"
)


def _det_sensitive_read(path: str, content: str) -> list[dict]:
    out = []
    for m in _SENSITIVE_PATH.finditer(content):
        out.append(_m(content, m.start(), "Reads SSH keys, browser profiles, cloud/wallet credentials or cookies."))
    return out


_PROMPT_INJECTION = re.compile(
    r"(?i)("
    r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|preceding)"
    r"|disregard\s+(?:all\s+)?(?:previous|prior|above|earlier|instructions)"
    r"|before\s+using\s+any\s+other\s+tool"
    r"|you\s+must\s+(?:call|use|first|not\s+tell|never\s+tell)"
    r"|system\s+prompt"
    r"|(?:do\s+not|don'?t)\s+(?:tell|inform|reveal|mention|disclose)\s+(?:the\s+)?user"
    r"|pretend\s+to\s+be|act\s+as\s+(?:if|a|an)\b|you\s+are\s+now\s+a\b"
    r"|override\s+(?:the\s+)?(?:system|safety|instructions)"
    r"|\bsend\s+(?:all|the)\s+(?:data|contents?|output|context|env(?:ironment)?|credentials|tokens?)\b"
    r"|\bfirst\s+call\s+\S+[^\n]*\bwith\s+all\b"
    r")"
)


def _det_prompt_injection(path: str, content: str) -> list[dict]:
    out = []
    for lineno, line in enumerate(content.splitlines(), 1):
        if not any(q in line for q in ('"', "'", "`")):
            continue
        m = _PROMPT_INJECTION.search(line)
        if m:
            out.append({"line": lineno, "detail": "Instructions addressed to the model hidden in a string.", "evidence": line.strip()[:140], "severity": None})
    return out


# ------------------------------------------------------ dependency detectors

_POPULAR_PY = {
    "requests", "flask", "fastapi", "numpy", "pandas", "django", "boto3", "httpx",
    "openai", "langchain", "pydantic", "uvicorn", "starlette", "aiohttp", "sqlalchemy",
    "celery", "click", "redis", "psutil", "pyyaml", "setuptools", "pillow", "scipy",
    "matplotlib", "torch", "transformers", "pyjwt", "cryptography", "pytest", "jinja2",
    "gunicorn", "markdown", "python-memcached", "waitress", "anthropic", "tiktoken",
}
_POPULAR_NPM = {
    "express", "lodash", "react", "axios", "chalk", "commander", "fs-extra", "moment",
    "zod", "dotenv", "typescript", "next", "vue", "socket.io", "mongoose", "body-parser",
    "cors", "debug", "glob", "rimraf", "jest", "eslint", "webpack", "nodemon", "semver",
    "uuid", "node-fetch", "undici", "yaml", "jsonwebtoken", "tailwindcss", "vite",
}


def _levenshtein(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            best = min(best, v)
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def _typosquat_name(name: str, popular: set[str]) -> Optional[str]:
    n = name.strip().lower()
    if not n or n in popular or n.startswith("@"):
        return None
    for cand in popular:
        cap = 2 if len(cand) >= 6 else 1
        if abs(len(n) - len(cand)) > cap:
            continue
        d = _levenshtein(n, cand, cap)
        if d <= cap:
            return f"'{name}' is {d} edit(s) from popular package '{cand}' (possible typosquat)"
    return None


def _det_typosquat(path: str, content: str) -> list[dict]:
    out = []
    if _is_requirements(path):
        for lineno, line in enumerate(content.splitlines(), 1):
            name = re.split(r"[=<>~!\[; #@ ]", line.split("#")[0].strip())[0]
            hit = _typosquat_name(name, _POPULAR_PY)
            if hit:
                out.append({"line": lineno, "detail": hit, "evidence": line.strip()[:140], "severity": None})
    elif _is_package_json(path):
        for m in re.finditer(r"(?i)\"(dev[Dd]ependencies|dependencies)\"\s*:\s*\{", content):
            block, _ = _read_block(content, content.find("{", m.start()))
            for pm in re.finditer(r"\"([^\"]+)\"\s*:\s*\"[^\"]*\"", block):
                hit = _typosquat_name(pm.group(1), _POPULAR_NPM)
                if hit:
                    out.append({"line": _line_of(content, m.start() + pm.start() + 1), "detail": hit, "evidence": pm.group(0)[:140], "severity": None})
    return out


def _det_install_script(path: str, content: str) -> list[dict]:
    if not _is_package_json(path):
        return []
    out = []
    for m in re.finditer(r"\"(preinstall|postinstall|install|prepare)\"\s*:\s*\"([^\"]*)\"", content):
        script = m.group(2)
        if re.search(r"(?i)\b(curl|wget|powershell|nc\s)\b|https?://|node\s+-e|base64\s+-d|\| *(ba)?sh\b", script):
            out.append(_m(content, m.start(), f"npm '{m.group(1)}' script fetches/executes remote code: {script[:80]}"))
    return out

# ----------------------------------------------------------- tool extraction

@dataclass
class _ToolRec:
    name: str
    description: str
    annotations: list[str]
    risks: list[str]
    file: str
    line: int
    body: str


_PY_TOOL_DEC = re.compile(r"@(?:[\w.]+\.)?tool\b")
_PY_DEF = re.compile(r"\bdef\s+(\w+)\s*\(([^)]*)\)\s*(?:->[^:]+)?:", re.DOTALL)
_HINT_KW = re.compile(
    r"(readOnlyHint|destructiveHint|idempotentHint|openWorldHint|read_only_hint|"
    r"destructive_hint|idempotent_hint|open_world_hint)\s*[:=]\s*(True|False|true|false)"
)


def _parse_hints(text: str) -> list[str]:
    canon = {"read_only_hint": "readOnlyHint", "destructive_hint": "destructiveHint",
             "idempotent_hint": "idempotentHint", "open_world_hint": "openWorldHint"}
    hints = []
    for m in _HINT_KW.finditer(text):
        key = canon.get(m.group(1), m.group(1))
        hints.append(f"{key}={m.group(2).lower()}")
    return hints


def _py_docstring(content: str, def_end: int) -> str:
    seg = content[def_end:def_end + 900]
    m = re.search(r"\"\"\"([\s\S]{0,400}?)\"\"\"|'''([\s\S]{0,400}?)'''", seg)
    if not m:
        return ""
    doc = (m.group(1) or m.group(2) or "").strip()
    return re.sub(r"\s+", " ", doc)


def _py_body(content: str, def_start: int) -> str:
    start = content.rfind("\n", 0, def_start) + 1
    lines = content[start:].splitlines()
    body: list[str] = []
    for ln in lines[1:120]:
        if ln and not ln[0].isspace():
            break
        body.append(ln)
    return "\n".join(body[:120])


def _extract_py_tools(path: str, content: str) -> list[_ToolRec]:
    recs = []
    for m in _PY_TOOL_DEC.finditer(content):
        idx = m.end()
        args = ""
        while idx < len(content) and content[idx] in " \t\r\n\\":
            idx += 1
        if idx < len(content) and content[idx] == "(":
            args, idx = _read_block(content, idx)
        dm = _PY_DEF.search(content[idx:idx + 600])
        if not dm:
            continue
        fn_name, sig = dm.group(1), dm.group(2)
        def_abs = idx + dm.start()
        nm = re.search(r"[\"']?name[\"']?\s*[:=]\s*[\"']([\w\-.:]+)[\"']", args)
        dsc = re.search(r"[\"']?description[\"']?\s*[:=]\s*[\"'](.+?)[\"']", args)
        desc = dsc.group(1) if dsc else _py_docstring(content, def_abs)
        recs.append(_ToolRec(
            name=nm.group(1) if nm else fn_name,
            description=desc[:400],
            annotations=_parse_hints(args),
            risks=[],
            file=path,
            line=_line_of(content, m.start()),
            body=_py_body(content, def_abs),
        ))
    return recs


def _extract_js_tools(path: str, content: str) -> list[_ToolRec]:
    recs = []
    for m in re.finditer(r"(?:server|mcp|app|connection)\.tool\s*\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']*)[\"']", content):
        recs.append(_ToolRec(m.group(1), m.group(2)[:400], [], [], path, _line_of(content, m.start()), content[m.end():m.end() + 1200]))
    for m in re.finditer(r"(?:registerTool|addTool)\s*\(\s*[\"']([^\"']+)[\"']\s*,?\s*", content):
        k = content.find("{", m.end() - 1)
        cfg, end = ("", m.end())
        if k != -1 and k < m.end() + 40:
            cfg, end = _read_block(content, k)
        dsc = re.search(r"description\s*:\s*[\"']([^\"']*)[\"']", cfg)
        recs.append(_ToolRec(
            m.group(1), (dsc.group(1) if dsc else "")[:400], _parse_hints(cfg), [],
            path, _line_of(content, m.start()), content[end:end + 1200],
        ))
    return recs


def _extract_tool_records(files: dict[str, str]) -> list[_ToolRec]:
    recs: list[_ToolRec] = []
    seen: set[tuple[str, str]] = set()
    for path, content in files.items():
        if not isinstance(content, str) or "node_modules/" in path.replace("\\", "/"):
            continue
        p = path.replace("\\", "/")
        if p.endswith(".py"):
            new = _extract_py_tools(path, content)
        elif p.endswith(_CODE_EXT):
            new = _extract_js_tools(path, content)
        else:
            new = []
        for rec in new:
            key = (rec.name, path)
            if key not in seen:
                seen.add(key)
                recs.append(rec)
    return recs


def _extract_tools(bundle: SourceBundle) -> list[ToolInfo]:
    return [
        ToolInfo(name=r.name, description=r.description, annotations=list(r.annotations), risks=list(r.risks))
        for r in _extract_tool_records(bundle.files)
    ]


# ---------------------------------------------------------- tool-scoped rules

_DESTRUCTIVE_NAME = re.compile(r"(?i)(delete|drop|remove|flush|reset|purge|truncate|wipe|erase|destroy|cleanup|kill)")
_SHELL_NAME = re.compile(r"(?i)\b(bash|sh|zsh|shell|cmd|command|terminal|exec|execute_command|run_command|run_shell)\b")
_SHELL_BODY = re.compile(r"(?i)subprocess|os\.system|shell\s*=\s*True|Popen|child_process|execSync|spawnSync|(?<![\w.])eval\s*\(")
_SAFE_DESC = re.compile(r"(?i)read[- ]?only|safe|harmless|non[- ]?destructive|passive|does not (?:modify|write|execute)|never (?:modifies|writes|executes)")
_UNSAFE_BODY = re.compile(
    r"open\s*\([^)]*[\"'][wa]|os\.(?:remove|unlink)|shutil\.rmtree|subprocess\.|os\.system|"
    r"child_process|writeFileSync|(?<![\w.])exec\s*\(|(?<![\w.])eval\s*\(|\.write\s*\("
)


def _tool_rules(recs: list[_ToolRec]) -> list[dict]:
    """Findings derived from extracted tool records (file:line known)."""
    out = []
    for rec in recs:
        # prompt injection carried in the description even if spread over lines
        if _PROMPT_INJECTION.search(rec.description):
            rec.risks.append("prompt-injection")
            out.append({
                "rule_id": "PROMPT-INJECTION", "file": rec.file, "line": rec.line,
                "detail": f"Tool '{rec.name}' description contains model-directed instructions.",
                "evidence": rec.description[:140], "severity": None,
            })
        if _DESTRUCTIVE_NAME.search(rec.name):
            rec.risks.append("destructive")
            ro = next((a.split("=")[1] == "true" for a in rec.annotations if a.startswith("readOnlyHint=")), None)
            dh = next((a.split("=")[1] == "true" for a in rec.annotations if a.startswith("destructiveHint=")), None)
            if ro is True:
                detail = "destructive tool misannotated with readOnlyHint=true"
            elif dh is False:
                detail = "destructive tool annotated destructiveHint=false"
            elif ro is None and dh is None:
                detail = "destructive tool lacks readOnlyHint/destructiveHint annotations"
            else:
                detail = ""
            if detail:
                out.append({
                    "rule_id": "DESTRUCTIVE-UNANNOTATED", "file": rec.file, "line": rec.line,
                    "detail": f"Tool '{rec.name}': {detail}.", "evidence": f"def {rec.name}", "severity": None,
                })
        if _SHELL_NAME.search(rec.name):
            rec.risks.append("shell")
            sig = rec.body.split("(", 1)[1][:300] if "(" in rec.body else ""
            if _SHELL_BODY.search(rec.body) or re.search(r"(?i)\b(command|cmd|script|shell)\w*\s*:\s*str", sig):
                out.append({
                    "rule_id": "SHELL-TOOL", "file": rec.file, "line": rec.line,
                    "detail": f"Tool '{rec.name}' executes shell commands from string arguments.",
                    "evidence": f"tool {rec.name}", "severity": None,
                })
        if _SAFE_DESC.search(rec.description) and _UNSAFE_BODY.search(rec.body):
            rec.risks.append("description-mismatch")
            out.append({
                "rule_id": "DESC-MISMATCH", "file": rec.file, "line": rec.line,
                "detail": f"Tool '{rec.name}' described as safe/read-only but its code writes or executes.",
                "evidence": rec.description[:140], "severity": None,
            })
        if re.search(r"open\s*\([^)]*[\"'][wa]|os\.(?:remove|unlink)|shutil\.rmtree|writeFileSync", rec.body):
            rec.risks.append("filesystem-write")
    return out


# --------------------------------------------------------------- rule registry

def _rule(rule_id: str, title: str, severity: Severity, description: str, remediation: str, detector) -> Rule:
    return Rule(rule_id=rule_id, title=title, severity=severity, description=description,
                remediation=remediation, detector=detector)


@dataclass
class Rule:
    rule_id: str
    title: str
    severity: Severity
    description: str
    remediation: str
    detector: Optional[Callable[[str, str], list[dict]]]


RULES: list[Rule] = [
    _rule("EVAL-EXEC", "Dynamic code execution via eval()/exec()", Severity.HIGH,
          "Server code calls eval()/exec() on dynamically constructed input, enabling arbitrary code execution.",
          "Remove dynamic code execution; parse structured input instead, or sandbox behind explicit user approval.",
          _det_eval_exec),
    _rule("SHELL-EXEC", "Shell command execution from server code", Severity.HIGH,
          "Server code invokes a system shell or spawns external processes.",
          "Avoid shelling out; if unavoidable, use argument lists (no shell=True) with an allowlisted binary and validated arguments.",
          _det_shell_exec),
    _rule("ENCODED-EXEC", "Base64-encoded payload passed to dynamic execution", Severity.CRITICAL,
          "Base64/codec-decoded data is decoded and executed, hiding the payload from review.",
          "Decode-and-execute patterns hide payloads from review; remove them and ship readable code.",
          _det_encoded_exec),
    _rule("DYNAMIC-IMPORT", "Dynamic import of a computed module name", Severity.HIGH,
          "__import__/importlib resolves a module from a variable, allowing hidden code to load at runtime.",
          "Import modules statically; validate any dynamic module names against a fixed allowlist.",
          _det_dynamic_import),
    _rule("OBFUSCATION", "Large obfuscated (hex/base64) string literal", Severity.MEDIUM,
          "A very long hex/base64 literal embeds an opaque payload reviewers cannot inspect.",
          "Replace obfuscated blobs with readable constants or data files reviewers can inspect.",
          _det_obfuscation),
    _rule("NET-EXFIL", "Network exfiltration of secrets to an untrusted endpoint", Severity.CRITICAL,
          "Server sends environment/credential data to a non-allowlisted or known exfiltration host.",
          "Remove outbound posts of environment/credential data; restrict egress to documented, allowlisted APIs.",
          _det_net_exfil),
    _rule("ENV-HARVEST", "Wholesale environment variable harvesting", Severity.HIGH,
          "The entire process environment is collected, exposing all secrets at once.",
          "Read only the specific variables the tool needs; never return the full environment to callers.",
          _det_env_harvest),
    _rule("HARDCODED-SECRET", "Hardcoded credential in source", Severity.CRITICAL,
          "Credential material (API key, password, private key) is committed in source code.",
          "Revoke the exposed credential and load secrets from environment or a secret manager at runtime.",
          _det_hardcoded_secret),
    _rule("DOTENV-EXPOSURE", ".env file read at runtime", Severity.MEDIUM,
          "Server code reads .env file contents at runtime, which can leak secrets into tool outputs.",
          "Load configuration via the process environment, not by reading .env inside server code.",
          _det_dotenv),
    _rule("FS-WRITE-ESCAPE", "Filesystem write outside the workspace", Severity.MEDIUM,
          "A write/delete targets an absolute path or escapes the workspace via path traversal.",
          "Confine writes to a dedicated workspace directory; reject absolute paths and '..' traversal.",
          _det_fs_write),
    _rule("SENSITIVE-READ", "Access to sensitive credential/profile files", Severity.HIGH,
          "Code reads SSH keys, browser profiles, cookies, cloud credentials or wallet files.",
          "Never read SSH keys, browser profiles, or wallet data; restrict file access to declared workspace paths.",
          _det_sensitive_read),
    _rule("PROMPT-INJECTION", "Prompt injection instructions in tool description", Severity.CRITICAL,
          "Tool description/string contains instructions addressed to the model (e.g. 'ignore previous instructions').",
          "Rewrite the description to describe functionality only; remove instructions addressed to the model/agent.",
          _det_prompt_injection),
    _rule("DESTRUCTIVE-UNANNOTATED", "Destructive tool missing/incorrect safety annotations", Severity.MEDIUM,
          "A tool whose name implies deletion/reset lacks readOnlyHint/destructiveHint annotations or contradicts them.",
          "Set readOnlyHint=false and destructiveHint=true (and require explicit confirmation) on destructive tools.",
          None),
    _rule("SHELL-TOOL", "Tool executes shell commands from string arguments", Severity.HIGH,
          "A bash/sh/cmd-style tool passes free-form string arguments to a shell.",
          "Replace free-form shell tools with narrow, parameterized operations and strict input validation.",
          None),
    _rule("DESC-MISMATCH", "Tool description contradicts its code behavior", Severity.MEDIUM,
          "Tool claims to be read-only/safe while its code writes, deletes or executes.",
          "Make the description accurately reflect side effects; misleading 'read-only' labels bypass human review.",
          None),
    _rule("TYPOSQUAT", "Dependency name mimics a popular package (typosquat)", Severity.HIGH,
          "A declared dependency is a near-miss spelling of a widely used package.",
          "Verify the exact package spelling and publisher; install the canonical package only.",
          _det_typosquat),
    _rule("INSTALL-SCRIPT", "Package install script executes remote code", Severity.CRITICAL,
          "npm preinstall/postinstall script downloads and pipes remote code into a shell.",
          "Remove curl|bash-style install scripts; run trusted build steps only, pinned and reviewed.",
          _det_install_script),
]

_TOOL_RULE_IDS = {"PROMPT-INJECTION", "DESTRUCTIVE-UNANNOTATED", "SHELL-TOOL", "DESC-MISMATCH"}

# ------------------------------------------------------------------- scoring


def score_findings(findings) -> tuple[int, RiskLevel]:
    """Weighted score (capped 100) and risk level at thresholds 70/40/15."""
    score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in findings))
    if score >= 70:
        return score, RiskLevel.CRITICAL
    if score >= 40:
        return score, RiskLevel.HIGH
    if score >= 15:
        return score, RiskLevel.MEDIUM
    return score, RiskLevel.LOW


def _summary(findings: list[Finding], n_files: int, n_tools: int) -> str:
    if not findings:
        return f"No security findings detected across {n_files} file(s); {n_tools} tool(s) extracted look clean."
    counts = Counter(f.severity for f in findings)
    parts = [f"{counts[s]} {s.value}" for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO) if counts[s]]
    top = findings[0]
    return (
        f"{len(findings)} finding(s) ({', '.join(parts)}) across {n_files} file(s), {n_tools} tool(s) extracted. "
        f"Most severe: {top.rule_id} — {top.title.lower()}."
    )


# ----------------------------------------------------------------- entrypoint


def analyze_bundle(bundle: SourceBundle) -> AnalysisResult:
    files = {p: (c if isinstance(c, str) else "") for p, c in (bundle.files or {}).items()}
    recs = _extract_tool_records(files)

    # tool-scoped rules mutate rec.risks, so run them before ToolInfo copies are built
    tool_rule_matches = _tool_rules(recs)
    tools = [
        ToolInfo(name=r.name, description=r.description, annotations=list(r.annotations), risks=list(r.risks))
        for r in recs
    ]

    raw: list[dict] = []
    for rule in RULES:
        if rule.detector is None:
            continue
        for path, content in files.items():
            if not (_is_code(path) or _is_shell_script(path) or _is_requirements(path) or _is_package_json(path)):
                continue
            matches = rule.detector(path, content)
            for match in matches[:MAX_PER_RULE_PER_FILE]:
                raw.append({"rule": rule, "file": path, **match})

    # tool-scoped rule matches collected above
    for match in tool_rule_matches:
        rule = next(r for r in RULES if r.rule_id == match["rule_id"])
        raw.append({"rule": rule, "file": match["file"], "line": match["line"],
                    "detail": match["detail"], "evidence": match["evidence"], "severity": None})

    findings: list[Finding] = []
    seen: set[tuple[str, str, int]] = set()
    for m in raw:
        rule: Rule = m["rule"]
        key = (rule.rule_id, m["file"], m["line"])
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(
            id=f"{rule.rule_id}:{m['file']}:{m['line']}",
            rule_id=rule.rule_id,
            title=rule.title,
            severity=m.get("severity") or rule.severity,
            description=f"{rule.description} {m['detail']}".strip(),
            remediation=rule.remediation,
            evidence=(m.get("evidence") or None),
            file=m["file"],
            line=m["line"],
        ))

    findings.sort(key=lambda f: (_SEV_ORDER[f.severity], f.file or "", f.line or 0))

    # Map file-level findings back onto the tools they implicate, so the report's
    # per-tool risk chips agree with the findings list and the Cedar generator's
    # risk classification (cedar.split_tools reads tool.risks first).
    #
    # Two independent signals, because name matching alone silently under-reports:
    # a finding's evidence is the offending SOURCE LINE (e.g. `return
    # str(eval(expr))`), which never names the function enclosing it. That left
    # `run_expression` with zero risk tags while an EVAL-EXEC finding sat inside
    # its body -- and the generated Cedar policy then PERMITTED the tool that
    # calls eval(). Containment by line span is the signal that actually holds.
    _TAG_BY_RULE = {
        "PROMPT-INJECTION": "prompt-injection",
        "NET-EXFIL": "exfiltration",
        "EVAL-EXEC": "eval",
        "SHELL-EXEC": "shell",
        "ENV-HARVEST": "env-harvest",
        "DESTRUCTIVE-UNANNOTATED": "destructive",
        "HARDCODED-SECRET": "secret",
        "SENSITIVE-READ": "sensitive-read",
        "FS-WRITE-ESCAPE": "filesystem-write",
        "SHELL-TOOL": "shell",
        "DESC-MISMATCH": "misleading-description",
    }
    # Source span of each tool, from its decorator/registration line through its
    # captured body. Capped at the next tool in the same file so one finding is
    # never charged to two tools.
    spans: list[tuple[int, int]] = []
    for rec in recs:
        start = rec.line
        end = start + rec.body.count("\n") + 2  # decorator, def and signature slack
        for other in recs:
            if other is not rec and other.file == rec.file and start < other.line <= end:
                end = other.line - 1
        spans.append((start, end))

    for finding in findings:
        tag = _TAG_BY_RULE.get(finding.rule_id)
        if not tag:
            continue
        blob = " ".join(
            part
            for part in (finding.title, finding.description, finding.evidence or "", finding.file or "")
            if part
        )
        for tool, rec, (start, end) in zip(tools, recs, spans):
            # Signal 1: the finding sits inside this tool's source span. Catches
            # findings whose evidence is a bare line of code (eval, subprocess,
            # requests.post) that never mentions the enclosing function.
            enclosed = (
                finding.file == rec.file
                and finding.line is not None
                and start <= finding.line <= end
            )
            # Signal 2: the finding text names the tool. Catches tool-scoped
            # rules and references from outside the tool's own body.
            named = len(tool.name) >= 3 and tool.name in blob
            if (enclosed or named) and tag not in tool.risks:
                tool.risks.append(tag)

    score, level = score_findings(findings)
    return AnalysisResult(
        findings=findings,
        tools=tools,
        risk_score=score,
        risk_level=level,
        summary=_summary(findings, len(files), len(tools)),
    )
