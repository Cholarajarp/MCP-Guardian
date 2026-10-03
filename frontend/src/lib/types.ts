/** Shared TypeScript contract — must mirror backend/app/models.py (camelCase JSON). */
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type SourceType = "github" | "npm" | "paste";
export type ScanStatus = "pending" | "scanning" | "complete" | "error";

export interface ScanRequest {
  sourceType: SourceType;
  /** "owner/repo" for github, package name for npm, label for paste */
  source: string;
  /** branch / tag / commit (github only) */
  ref?: string;
  /** paste mode: path -> content */
  files?: Record<string, string>;
}

export interface ServerInfo {
  name: string;
  sourceType: SourceType;
  sourceRef: string;
  version?: string;
  description?: string;
}

export interface Finding {
  id: string;
  ruleId: string;
  title: string;
  severity: Severity;
  description: string;
  remediation: string;
  evidence?: string;
  file?: string;
  line?: number;
}

export interface ToolInfo {
  name: string;
  description: string;
  annotations: string[];
  risks: string[];
}

export interface PolicyDecision {
  tool: string;
  effect: "allow" | "require-approval";
  reason: string;
}

export interface AnalysisResult {
  findings: Finding[];
  tools: ToolInfo[];
  riskScore: number; // 0-100
  riskLevel: RiskLevel;
  summary: string;
}

export interface ScanResult {
  id: string;
  status: ScanStatus;
  request: ScanRequest;
  server: ServerInfo;
  riskScore: number;
  riskLevel: RiskLevel;
  findings: Finding[];
  tools: ToolInfo[];
  /** Per-tool decisions under the generated Cedar policy (enforcement preview). */
  policyDecisions?: PolicyDecision[];
  cedarPolicy: string;
  narrative: string;
  error?: string;
  createdAt: string;
  durationMs?: number;
}
