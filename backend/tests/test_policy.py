"""Offline tests for the Cedar generator and the risk narrator.

No network, no AWS credentials: the narrator's Bedrock path is exercised only
through its fallback behavior (env unset / boto3 import forced to fail).
"""
from __future__ import annotations

import sys

from app.agents.narrator import generate_narrative
from app.models import (
    AnalysisResult,
    Finding,
    RiskLevel,
    ServerInfo,
    Severity,
    SourceType,
    ToolInfo,
)
from app.policy.cedar import generate_cedar_policy, split_tools, validate_policy


def _server() -> ServerInfo:
    return ServerInfo(
        name="github-search",
        source_type=SourceType.GITHUB,
        source_ref="acme/github-search",
        version="1.2.0",
    )


def _finding(tool_hint: str = "run_shell") -> Finding:
    return Finding(
        id="f1",
        rule_id="SHELL-EXEC",
        title="Shell execution from server code",
        severity=Severity.HIGH,
        description=f"subprocess call reachable from tool '{tool_hint}'.",
        remediation="Sandbox behind explicit approval.",
        file="server.py",
        line=42,
    )


def _risky_analysis() -> AnalysisResult:
    """4-tool server: 2 safe, 2 risky."""
    return AnalysisResult(
        findings=[_finding()],
        tools=[
            ToolInfo(name="search_docs", description="Search documents", risks=[]),
            ToolInfo(name="list_records", description="List records", risks=[]),
            ToolInfo(name="run_shell", description="Run a shell command", risks=["shell", "destructive"]),
            ToolInfo(name="write_file", description="Write a file", risks=["filesystem-write"]),
        ],
        risk_score=26,
        risk_level=RiskLevel.MEDIUM,
        summary="1 findings across 2 files.",
    )


class TestCedarGenerator:
    def test_risky_case_contains_permit_and_forbid(self):
        policy = generate_cedar_policy(_server(), _risky_analysis())
        assert "namespace MCP {" in policy
        assert 'action == Action::"invoke"' in policy
        # Safe tools permitted.
        for tool in ("search_docs", "list_records"):
            assert f"resource.tool in [\"{tool}\"]" in policy
        # Risky tools forbidden.
        assert 'resource.tool in ["run_shell"]' in policy
        assert 'resource.tool in ["write_file"]' in policy
        assert policy.count("permit(") == 2
        assert policy.count("forbid(") == 2
        # Human-in-the-loop escape hatch on the forbid policies.
        assert "context.approved == true" in policy
        # Header comments carry server identity + risk score.
        assert "github-search" in policy
        assert "26/100" in policy
        # Entity types declared in comments.
        assert 'entity Server = {"name": String};' in policy
        assert 'entity Invocation = {"tool": String, "approved": Bool};' in policy

    def test_validate_policy_passes_on_generated_output(self):
        policy = generate_cedar_policy(_server(), _risky_analysis())
        assert validate_policy(policy) == []
        assert "Lint (validate_policy): OK" in policy

    def test_empty_tools_default_deny(self):
        policy = generate_cedar_policy(_server(), AnalysisResult(findings=[], tools=[]))
        assert "TODO" in policy
        assert "permit(" not in policy
        assert 'forbid(principal, action == Action::"invoke", resource);' in policy
        assert validate_policy(policy) == []

    def test_finding_linked_tool_is_risky_without_risk_tags(self):
        analysis = AnalysisResult(
            findings=[_finding("run_shell")],
            tools=[ToolInfo(name="run_shell", risks=[])],
            risk_score=18,
            risk_level=RiskLevel.MEDIUM,
        )
        safe, risky = split_tools(analysis)
        assert [t.name for t in safe] == []
        assert [t.name for t in risky] == ["run_shell"]
        policy = generate_cedar_policy(_server(), analysis)
        assert policy.count("forbid(") == 1
        assert "permit(" not in policy

    def test_tool_names_with_special_chars_stay_quoted(self):
        analysis = AnalysisResult(
            findings=[],
            tools=[
                ToolInfo(name='fs/write?file"2', risks=[]),
                ToolInfo(name="weird {brace} tool", risks=["shell"]),
            ],
        )
        policy = generate_cedar_policy(_server(), analysis)
        assert '"fs/write?file\\"2"' in policy
        assert '"weird {brace} tool"' in policy
        assert validate_policy(policy) == []

    def test_lint_catches_broken_policy_text(self):
        # Unclosed brace.
        assert validate_policy("permit(principal, action, resource) when {") != []
        # Unterminated string literal.
        assert validate_policy(
            'permit(principal, action, resource) when { resource.tool in ["a] };'
        ) != []
        # Well-formed minimal policy set is clean.
        assert validate_policy("namespace MCP { permit(principal, action, resource); }") == []


class TestNarrator:
    _AWS_VARS = (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "BEDROCK_MODEL_ID",
    )

    def _clear_aws_env(self, monkeypatch):
        for var in self._AWS_VARS:
            monkeypatch.delenv(var, raising=False)

    def test_template_fallback_when_env_unset(self, monkeypatch):
        self._clear_aws_env(monkeypatch)
        server, analysis = _server(), _risky_analysis()
        narrative = generate_narrative(server, analysis)
        assert narrative.strip()
        assert server.name in narrative
        assert "26/100" in narrative
        assert "run_shell" in narrative
        # Deterministic: identical inputs produce identical output.
        assert generate_narrative(server, analysis) == narrative

    def test_fallback_when_bedrock_call_fails(self, monkeypatch):
        self._clear_aws_env(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        # Forces `import boto3` inside the narrator to raise ImportError.
        monkeypatch.setitem(sys.modules, "boto3", None)
        narrative = generate_narrative(_server(), _risky_analysis())  # must not raise
        assert narrative.strip()
        assert "26/100" in narrative
