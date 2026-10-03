import type { RiskLevel, Severity } from "@/lib/types";

/** Tiny class joiner (keeps us independent of a clsx/tailwind-merge dep). */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

export interface SeverityMeta {
  label: string;
  /** Solid badge: severity token fill + the ink (white / brand-contrast) that passes on it. */
  badge: string;
  /** Tinted chip on a solid card: --severity-*-subtle rgba fill — never a blur. */
  soft: string;
  /** 3px left accent bar background. */
  accent: string;
  /** Colored text, theme-aware via the severity token. */
  text: string;
  /** SVG stroke class (risk gauge arc). */
  stroke: string;
}

export const SEVERITY_META: Record<Severity, SeverityMeta> = {
  critical: {
    label: "Critical",
    badge: "bg-critical text-critical-ink",
    soft: "bg-[color:var(--severity-critical-subtle)] text-critical",
    accent: "bg-critical",
    text: "text-critical",
    stroke: "stroke-critical",
  },
  high: {
    label: "High",
    badge: "bg-high text-high-ink",
    soft: "bg-[color:var(--severity-high-subtle)] text-high",
    accent: "bg-high",
    text: "text-high",
    stroke: "stroke-high",
  },
  medium: {
    label: "Medium",
    badge: "bg-medium text-medium-ink",
    soft: "bg-[color:var(--severity-medium-subtle)] text-medium",
    accent: "bg-medium",
    text: "text-medium",
    stroke: "stroke-medium",
  },
  low: {
    label: "Low",
    badge: "bg-low text-low-ink",
    soft: "bg-[color:var(--severity-low-subtle)] text-low",
    accent: "bg-low",
    text: "text-low",
    stroke: "stroke-low",
  },
  info: {
    label: "Info",
    badge: "bg-info text-info-ink",
    soft: "bg-[color:var(--severity-info-subtle)] text-info",
    accent: "bg-info",
    text: "text-info",
    stroke: "stroke-info",
  },
};

export interface RiskLevelMeta {
  label: string;
  badge: string;
  text: string;
  stroke: string;
  accent: string;
  /** One-line verdict shown under the gauge. */
  verdict: string;
}

/** Risk levels share the severity tokens; "low risk" is a positive result, so green. */
export const RISK_LEVEL_META: Record<RiskLevel, RiskLevelMeta> = {
  critical: {
    label: "Critical risk",
    badge: SEVERITY_META.critical.badge,
    text: "text-critical",
    stroke: "stroke-critical",
    accent: "bg-critical",
    verdict: "Do not connect this server to an agent",
  },
  high: {
    label: "High risk",
    badge: SEVERITY_META.high.badge,
    text: "text-high",
    stroke: "stroke-high",
    accent: "bg-high",
    verdict: "Significant risks — review before connecting",
  },
  medium: {
    label: "Medium risk",
    badge: SEVERITY_META.medium.badge,
    text: "text-medium",
    stroke: "stroke-medium",
    accent: "bg-medium",
    verdict: "Review findings before connecting",
  },
  low: {
    label: "Low risk",
    badge: "bg-positive text-positive-ink",
    text: "text-positive",
    stroke: "stroke-positive",
    accent: "bg-positive",
    verdict: "No significant risks detected",
  },
};

/** Maps a free-form risk tag from ToolInfo.risks to a tinted chip style. */
export function riskChipClass(risk: string): string {
  const r = risk.toLowerCase();
  if (/(inject|exfil|credential|secret|env)/.test(r)) return SEVERITY_META.critical.soft;
  if (/(eval|exec|destruct|delete|write|sql|command)/.test(r)) return SEVERITY_META.high.soft;
  if (/(net|unannotat|annotat|fetch|post)/.test(r)) return SEVERITY_META.medium.soft;
  return SEVERITY_META.info.soft;
}

export function formatDuration(ms?: number): string | null {
  if (ms === undefined || ms === null) return null;
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Deterministic (fixed locale + UTC) so SSR and client agree. */
export function formatCreated(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(d)} UTC`;
}
