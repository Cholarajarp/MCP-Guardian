"""MCP Guardian — shared data contract.

All API JSON uses camelCase (pydantic alias generator). Frontend mirror:
frontend/src/lib/types.ts must stay in sync with this file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(str, Enum):
    GITHUB = "github"
    NPM = "npm"
    PASTE = "paste"


class ScanStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETE = "complete"
    ERROR = "error"


class ScanRequest(CamelModel):
    source_type: SourceType
    source: str  # "owner/repo" for github, package name for npm, label for paste
    ref: Optional[str] = None  # branch / tag / commit (github only)
    files: Optional[dict[str, str]] = None  # paste mode: path -> content


class ServerInfo(CamelModel):
    name: str
    source_type: SourceType
    source_ref: str
    version: Optional[str] = None
    description: Optional[str] = None


class SourceBundle(CamelModel):
    """Everything the fetcher hands to the analyzer."""
    server: ServerInfo
    files: dict[str, str]  # relative path -> text content
    fetched_at: datetime = Field(default_factory=_utcnow)


class Finding(CamelModel):
    id: str
    rule_id: str
    title: str
    severity: Severity
    description: str
    remediation: str
    evidence: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


class ToolInfo(CamelModel):
    name: str
    description: str = ""
    annotations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PolicyDecision(CamelModel):
    """Per-tool decision under the generated Cedar policy (UI enforcement preview)."""
    tool: str
    effect: str  # "allow" | "require-approval"
    reason: str


class AnalysisResult(CamelModel):
    findings: list[Finding]
    tools: list[ToolInfo]
    risk_score: int = Field(ge=0, le=100, default=0)
    risk_level: RiskLevel = RiskLevel.LOW
    summary: str = ""


class ScanResult(CamelModel):
    id: str
    status: ScanStatus
    request: ScanRequest
    server: ServerInfo
    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    findings: list[Finding] = Field(default_factory=list)
    tools: list[ToolInfo] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    cedar_policy: str = ""
    narrative: str = ""
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    duration_ms: Optional[int] = None
