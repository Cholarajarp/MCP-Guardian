"""Risk narrative generation — Amazon Bedrock with deterministic fallback.

Contract (unchanged): ``generate_narrative(server, analysis) -> str``.

  * With AWS credentials in the environment, calls Amazon Bedrock
    (``bedrock-runtime`` Converse API — model-agnostic, defaults to Amazon
    Nova Lite, works with Nova Pro/Micro and Claude too; <= 300 tokens,
    strict plain-text prompt) for a concise risk assessment.
  * Without credentials — or on ANY Bedrock failure — returns a deterministic
    template. This function NEVER raises.
"""
from __future__ import annotations

import os

from app.models import AnalysisResult, ServerInfo
from app.policy.cedar import split_tools
from app import guard

# Default to Amazon Nova Lite: ~$0.06/1M input + $0.24/1M output tokens
# (≈ $0.0001 per narrative) — the zero-cost-friendly choice for deployments.
_DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"

# Any of these present (and non-empty) means AWS credentials are available.
_AWS_CREDENTIAL_ENV = (
    "AWS_ACCESS_KEY_ID",
    "AWS_PROFILE",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
)


def _has_aws_credentials() -> bool:
    return any(os.environ.get(var) for var in _AWS_CREDENTIAL_ENV)


def _template(server: ServerInfo, analysis: AnalysisResult) -> str:
    """Deterministic local narrative (no timestamps, stable ordering)."""
    safe, risky = split_tools(analysis)
    top = analysis.findings[:5]
    bullets = "\n".join(
        f"- [{f.severity.value.upper()}] {f.title} ({f.rule_id})" for f in top
    ) or "- No significant findings detected."
    if analysis.tools:
        names = ", ".join(t.name for t in risky[:8]) or "none"
        approval = (
            f"{len(risky)} of {len(risky) + len(safe)} tools require explicit "
            f"approval under the generated Cedar policy: {names}."
        )
    else:
        approval = (
            "No tools were parsed, so the generated Cedar policy "
            "default-denies every tool invocation."
        )
    guidance = {
        "critical": "Do NOT connect this server without manual code review.",
        "high": "Do not connect this server without manual review and explicit tool approval.",
        "medium": "Review the findings before connecting; gate risky tools behind approval.",
        "low": "Low risk — still review the findings before connecting.",
    }.get(analysis.risk_level.value, "Review the findings before connecting.")
    narrative = (
        f"MCP Guardian assessed '{server.name}' ({server.source_type.value}:{server.source_ref}) "
        f"and scored it {analysis.risk_score}/100 ({analysis.risk_level.value} risk).\n"
        f"Key findings:\n{bullets}\n"
        f"{approval}\n"
        f"Recommendation: {guidance}\n\n"
        "A generated Cedar policy restricting this server's tools is attached — import it into "
        "an AWS Verified Permissions policy store to enforce the rules. Review the evidence "
        "and remediation steps before connecting this server to an agent."
    )
    if not _has_aws_credentials():
        narrative += (
            "\n(Amazon Bedrock narrative unavailable — no AWS credentials configured; "
            "this is the deterministic local template.)"
        )
    return narrative


def generate_narrative(server: ServerInfo, analysis: AnalysisResult) -> str:
    """AWS Bedrock narrative with graceful local fallback (no creds needed).

    Cost controls, in order: a content-addressed cache (a repeat scan of an
    unchanged server pays nothing), then a shared daily budget reservation.
    Either guard declining sends us to the deterministic template, which is a
    complete substitute -- so the product never fails on cost grounds.
    """
    if not _has_aws_credentials():
        return _template(server, analysis)

    cache_key = guard.narrative_cache_key(
        server.source_ref,
        analysis.risk_score,
        [f.rule_id for f in analysis.findings],
    )
    cached = guard.narrative_cache_get(cache_key)
    if cached:
        return cached

    # Reserve spend only after the cache misses, so cached reads are free.
    if not guard.try_consume_narrative_budget():
        return _template(server, analysis)

    try:
        import boto3  # noqa: PLC0415 — optional at runtime
        from botocore.config import Config  # noqa: PLC0415

        client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1",
            config=Config(read_timeout=15, connect_timeout=5, retries={"max_attempts": 1}),
        )
        findings_text = "\n".join(
            f"- {f.severity.value}/{f.rule_id}: {f.title} — {f.description}"
            for f in analysis.findings[:15]
        )
        safe, risky = split_tools(analysis)
        system = (
            "You are a security analyst reviewing MCP (Model Context Protocol) servers. "
            "Write a concise risk assessment (max 120 words) for a software developer "
            "deciding whether to connect this MCP server to their AI agent. "
            "Plain text only: no markdown, no headings, no code blocks. "
            "Lead with the verdict, then the 2-3 most important risks, "
            "then one actionable recommendation."
        )
        prompt = (
            f"Server: {server.name} ({server.source_type.value}:{server.source_ref})\n"
            f"Risk score: {analysis.risk_score}/100 ({analysis.risk_level.value})\n"
            f"Tools: {len(safe)} safe, {len(risky)} risky "
            f"({', '.join(t.name for t in risky[:10]) or 'none'})\n"
            f"Findings:\n{findings_text or '- none'}"
        )
        # Converse API: one code path for every Bedrock model family
        # (Amazon Nova Lite/Pro/Micro and Anthropic Claude alike).
        response = client.converse(
            modelId=os.environ.get("BEDROCK_MODEL_ID") or _DEFAULT_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0},
        )
        parts = response.get("output", {}).get("message", {}).get("content", [])
        text = "\n".join(
            block.get("text", "") for block in parts if isinstance(block, dict)
        ).strip()
        if not text:
            return _template(server, analysis)
        # Cache only real model output, so a paid call is never repeated for an
        # unchanged server + findings set.
        guard.narrative_cache_put(cache_key, text)
        return text
    except Exception:  # noqa: BLE001 — any Bedrock failure falls back to the template
        return _template(server, analysis)
