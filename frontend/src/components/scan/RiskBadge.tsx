import type { RiskLevel } from "../../lib/types";

const RISK_LABEL: Record<RiskLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

const RISK_CLASSES: Record<RiskLevel, string> = {
  low: "border-low text-low",
  medium: "border-medium text-medium",
  high: "border-high text-high",
  critical: "border-critical text-critical",
};

/** Solid risk chip — severity token colors, safe in dark and light. */
export function RiskBadge({ level, className = "" }: { level: RiskLevel; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium leading-5 ${RISK_CLASSES[level]} ${className}`}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {RISK_LABEL[level]}
    </span>
  );
}
