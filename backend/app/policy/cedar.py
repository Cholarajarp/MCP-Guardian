"""Cedar policy generation for MCP Guardian.

Turns a scan into ONE Cedar policy-set string, ready to paste into an AWS
Verified Permissions policy store:

  * SAFE tools  -> one ``permit`` policy each (no manual approval needed).
  * RISKY tools -> one ``forbid`` policy each; the forbid is lifted only when
    the request context carries ``approved == true`` (human-in-the-loop gate).
    A tool is RISKY when the analyzer attached any risk tag to it, or when a
    HIGH/CRITICAL finding references the tool by name ("finding-linked").
  * Everything else -> Cedar's implicit deny; when no tools can be parsed at
    all, an explicit conservative default-deny ``forbid`` is emitted instead.

Syntax follows the current Cedar reference guide (https://docs.cedarpolicy.com,
Cedar 4.x — policies/syntax-policy.html and policies/syntax-entity.html):
policies are ``permit``/``forbid`` statements ending in ``;``, conditions live
in ``when``/``unless`` clauses, string literals are double-quoted, and ``in``
tests set membership (``resource.tool in ["a", "b"]``). Every generated policy
set is syntax-linted with :func:`validate_policy` and the outcome is appended
as trailing comments, so any problem is visible right in the pasted artifact.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.models import AnalysisResult, ServerInfo, Severity, ToolInfo

NAMESPACE = "MCP"
_ACTION = 'Action::"invoke"'
_MAX_POLICIES = 100  # stay well under AWS Verified Permissions per-store quotas

# Findings at these severities "link" to any tool they mention by name.
_LINK_SEVERITIES = {Severity.HIGH, Severity.CRITICAL}

# Characters the lint tolerates outside string literals and comments.
_ALLOWED_SYMBOLS = set("()[]{};:,.@&|!=<>+-*/%_ \t\r\n")

_CLOSER = {")": "(", "]": "[", "}": "{"}
_OPENER = {"(": ")", "[": "]", "{": "}"}


def _cedar_string(value: str) -> str:
    """Escape ``value`` into a Cedar double-quoted string literal."""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in value)
    escaped = (
        cleaned.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _comment_safe(value: str) -> str:
    """Flatten user-controlled text so it cannot break a ``//`` comment line."""
    return "".join(ch if ch.isprintable() else " " for ch in str(value)).strip()


def _slug(value: str) -> str:
    """Deterministic, annotation-safe slug for @id values."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return (slug or "tool")[:40]


def _finding_linked_tools(analysis: AnalysisResult) -> set[str]:
    """Tool names mentioned in the text of HIGH/CRITICAL findings."""
    linked: set[str] = set()
    for finding in analysis.findings:
        if finding.severity not in _LINK_SEVERITIES:
            continue
        blob = " ".join(
            part
            for part in (
                finding.title,
                finding.description,
                finding.evidence or "",
                finding.file or "",
            )
            if part
        ).lower()
        for tool in analysis.tools:
            name = tool.name.strip().lower()
            # >= 3 chars keeps short tool names from substring-matching everywhere.
            if len(name) >= 3 and name in blob:
                linked.add(tool.name)
    return linked


def split_tools(analysis: AnalysisResult) -> tuple[list[ToolInfo], list[ToolInfo]]:
    """Partition the scanned tools into (safe, risky), preserving scan order.

    RISKY = the analyzer attached at least one risk tag, OR a HIGH/CRITICAL
    finding references the tool by name. Deduplicated by tool name.
    """
    linked = _finding_linked_tools(analysis)
    safe: list[ToolInfo] = []
    risky: list[ToolInfo] = []
    seen: set[str] = set()
    for tool in analysis.tools:
        if tool.name in seen:
            continue
        seen.add(tool.name)
        if tool.risks or tool.name in linked:
            risky.append(tool)
        else:
            safe.append(tool)
    return safe, risky


def validate_policy(text: str) -> list[str]:
    """Syntax-lint a Cedar policy set without a parser dependency.

    Character-level scanner reporting: unbalanced ``()``, ``[]``, ``{}``;
    unterminated string literals or block comments; unexpected characters
    outside strings/comments; identifier tokens that do not look like valid
    Cedar identifiers; and policies missing their terminating ``;``.

    Returns a list of human-readable problems (empty list == clean).
    """
    errors: list[str] = []
    depth = {"(": 0, "[": 0, "{": 0}
    line = 1
    i, n = 0, len(text)
    in_line_comment = in_block_comment = in_string = escape = False
    ident: list[str] = []
    ident_line = 0
    policies_started = 0
    policies_terminated = 0
    pending_policy = False

    def flush_ident() -> None:
        nonlocal ident_line, policies_started, pending_policy
        if not ident:
            return
        token = "".join(ident)
        ident.clear()
        if token[0].isdigit():
            if not token.isdigit():
                errors.append(
                    f"line {ident_line}: invalid identifier '{token}' "
                    "(must not start with a digit)"
                )
        elif not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            errors.append(f"line {ident_line}: invalid identifier '{token}'")
        if (
            token in ("permit", "forbid")
            and not in_string
            and not in_line_comment
            and not in_block_comment
            and depth["("] == 0
            and depth["["] == 0
        ):
            policies_started += 1
            pending_policy = True

    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            if in_line_comment:
                in_line_comment = False
            elif in_string:
                errors.append(f"line {line - 1}: unterminated string literal")
                in_string = False
                escape = False
        if in_line_comment:
            i += 1
            continue
        if in_block_comment:
            if text.startswith("*/", i):
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        # Normal state.
        if text.startswith("//", i):
            flush_ident()
            in_line_comment = True
            i += 2
            continue
        if text.startswith("/*", i):
            flush_ident()
            in_block_comment = True
            i += 2
            continue
        if ch == '"':
            flush_ident()
            in_string = True
            i += 1
            continue
        if ch == "'":
            errors.append(
                f"line {line}: single-quoted literal — Cedar strings use double quotes"
            )
            i += 1
            continue
        if ch.isalnum() or ch == "_":
            if not ident:
                ident_line = line
            ident.append(ch)
            i += 1
            continue
        flush_ident()
        if ch in depth:
            depth[ch] += 1
        elif ch in _CLOSER:
            open_ch = _CLOSER[ch]
            if depth[open_ch] <= 0:
                errors.append(f"line {line}: unbalanced '{ch}'")
            else:
                depth[open_ch] -= 1
        elif ch == ";":
            if depth["("] == 0 and depth["["] == 0 and pending_policy:
                policies_terminated += 1
                pending_policy = False
        elif ch not in _ALLOWED_SYMBOLS:
            errors.append(
                f"line {line}: unexpected character {ch!r} outside string/comment"
            )
        i += 1

    flush_ident()
    if in_string:
        errors.append("unterminated string literal at end of input (quotes not balanced)")
    if in_block_comment:
        errors.append("unterminated block comment at end of input")
    for open_ch, close_ch in _OPENER.items():
        if depth[open_ch] > 0:
            errors.append(
                f"unbalanced '{open_ch}' — {depth[open_ch]} '{close_ch}' never closed"
            )
    if pending_policy:
        errors.append("last policy is missing its terminating ';'")
    if policies_started == 0:
        errors.append("no permit/forbid policies found")
    return errors


def _header(server: ServerInfo, analysis: AnalysisResult) -> list[str]:
    version = _comment_safe(server.version) if server.version else "unspecified"
    summary = _comment_safe(analysis.summary) or "no summary"
    return [
        "// " + "=" * 74,
        "// MCP Guardian — generated Cedar policy set",
        f"// Server identity: {_comment_safe(server.name)}  "
        f"source: {server.source_type.value}:{_comment_safe(server.source_ref)}  "
        f"version: {version}",
        f"// Risk score: {analysis.risk_score}/100 ({analysis.risk_level.value}) — {summary}",
        f"// Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "// Target: AWS Verified Permissions policy store "
        "(Cedar syntax, https://docs.cedarpolicy.com)",
        "//",
        "// Schema to register with the policy store (entity types declared in comments):",
        f"//   namespace {NAMESPACE} {{",
        "//     entity User;",
        '//     entity Server = {"name": String};',
        '//     entity Invocation = {"tool": String, "approved": Bool};',
        "//     action invoke appliesTo { principal: User, resource: Invocation };",
        "//   }",
        "//",
        "// Authorization request shape:",
        f'//   principal: {NAMESPACE}::User::"<user id>"',
        f'//   action:    {NAMESPACE}::{_ACTION}',
        "//   resource:  MCP::Invocation whose `tool` attribute names the MCP tool",
        '//   context:   {"approved": Bool} — true only after explicit human approval',
        "// " + "=" * 74,
    ]


def generate_cedar_policy(server: ServerInfo, analysis: AnalysisResult) -> str:
    """Return a Cedar policy set restricting this MCP server's tools.

    One string containing the full namespace-wrapped policy set. The output is
    linted with :func:`validate_policy`; lint findings are appended as comments
    so the artifact stays display-safe and problems are visible on paste.
    """
    safe, risky = split_tools(analysis)
    truncated = False
    if len(safe) + len(risky) > _MAX_POLICIES:
        risky = risky[:_MAX_POLICIES]
        safe = safe[: _MAX_POLICIES - len(risky)]
        truncated = True

    lines: list[str] = []
    lines.extend(_header(server, analysis))

    if not analysis.tools:
        lines.extend(
            [
                "",
                "// TODO: MCP Guardian could not parse any tools from this server's source.",
                "//       Review the source manually, then add permit policies for the tools",
                "//       you actually want to allow. Until then, everything is denied.",
                "",
                f"namespace {NAMESPACE} {{",
                "    // Conservative default-deny: explicit forbid on every tool invocation.",
                '    @id("forbid-all-invoke")',
                f"    forbid(principal, action == {_ACTION}, resource);",
                "}",
            ]
        )
    else:
        lines.append("")
        lines.append(f"namespace {NAMESPACE} {{")
        if truncated:
            lines.append(
                f"    // NOTE: tool list truncated to {_MAX_POLICIES} entries "
                "to stay within policy-store quotas."
            )
        lines.append("")
        lines.append("    // ---- SAFE tools — permitted without manual approval ----")
        if not safe:
            lines.append("    // (none — every scanned tool carries risk)")
        for idx, tool in enumerate(safe, start=1):
            risks = f" — risks: {', '.join(tool.risks)}" if tool.risks else ""
            lines.append("")
            lines.append(f"    // SAFE tool '{_comment_safe(tool.name)}'{_comment_safe(risks)}")
            lines.append(f'    @id("permit-{idx}-{_slug(tool.name)}")')
            lines.append(f"    permit(principal, action == {_ACTION}, resource)")
            lines.append("    when {")
            lines.append(f"        resource.tool in [{_cedar_string(tool.name)}]")
            lines.append("    };")
        lines.append("")
        lines.append("    // ---- RISKY tools — forbidden unless context.approved == true ----")
        if not risky:
            lines.append("    // (none — no risk tags and no finding-linked tools)")
        for idx, tool in enumerate(risky, start=1):
            reason = (
                ", ".join(tool.risks) if tool.risks else "referenced by a high-severity finding"
            )
            lines.append("")
            lines.append(f"    // RISKY tool '{_comment_safe(tool.name)}' — {_comment_safe(reason)}")
            lines.append(f'    @id("forbid-{idx}-{_slug(tool.name)}")')
            lines.append(f"    forbid(principal, action == {_ACTION}, resource)")
            lines.append("    when {")
            lines.append(f"        resource.tool in [{_cedar_string(tool.name)}]")
            lines.append("    }")
            lines.append("    unless {")
            lines.append("        context has approved && context.approved == true")
            lines.append("    };")
        lines.append("")
        lines.append(
            "    // Default deny: Cedar denies any request that no permit policy allows,"
        )
        lines.append(
            "    // so tools not listed above (including unknown/new tools) are rejected."
        )
        lines.append("}")

    text = "\n".join(lines) + "\n"
    lint = validate_policy(text)
    if lint:
        text += f"// Lint (validate_policy): {len(lint)} issue(s) — review before applying:\n"
        text += "".join(f"//   - {error}\n" for error in lint)
    else:
        text += (
            "// Lint (validate_policy): OK — braces/quotes balanced, "
            "identifiers valid, policies terminated.\n"
        )
    return text
