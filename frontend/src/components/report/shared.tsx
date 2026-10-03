"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  ClipboardPaste,
  GitBranch,
  Package,
  Shield,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { RiskLevel, ScanStatus, ScanResult, Severity, SourceType } from "@/lib/types";
import { RISK_LEVEL_META, SEVERITY_META, cx } from "./severity";

/* ------------------------------------------------------------------ */
/* Motion entrance wrapper used to stagger page sections on mount.     */
/* ------------------------------------------------------------------ */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Section label — small uppercase kicker used at the top of cards.    */
/* ------------------------------------------------------------------ */
export function SectionLabel({
  icon: Icon,
  children,
  right,
}: {
  icon: LucideIcon;
  children: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
        <Icon size={14} className="text-brand" aria-hidden />
        {children}
      </span>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Severity badge — solid white-on-color pill.                         */
/* ------------------------------------------------------------------ */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em]",
        meta.badge,
      )}
    >
      {meta.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Risk badge (riskLevel) — icon graduates with severity.              */
/* ------------------------------------------------------------------ */
const RISK_BADGE_ICON: Record<RiskLevel, LucideIcon> = {
  critical: TriangleAlert,
  high: ShieldAlert,
  medium: Shield,
  low: ShieldCheck,
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  const meta = RISK_LEVEL_META[level];
  const Icon = RISK_BADGE_ICON[level];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.1em]",
        meta.badge,
      )}
    >
      <Icon size={12} strokeWidth={2.5} aria-hidden />
      {meta.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Status pill.                                                        */
/* ------------------------------------------------------------------ */
const STATUS_META: Record<ScanStatus, { label: string; dot: string; pulse?: boolean }> = {
  pending: { label: "Pending", dot: "bg-muted", pulse: true },
  scanning: { label: "Scanning", dot: "bg-brand", pulse: true },
  complete: { label: "Complete", dot: "bg-positive" },
  error: { label: "Failed", dot: "bg-critical" },
};

export function StatusPill({ status }: { status: ScanStatus }) {
  const meta = STATUS_META[status];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-muted">
      <span
        className={cx("size-1.5 rounded-full", meta.dot, meta.pulse && "animate-pulse")}
        aria-hidden
      />
      {meta.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Source chip — github / npm / paste + sourceRef.                     */
/* ------------------------------------------------------------------ */
const SOURCE_ICON: Record<SourceType, LucideIcon> = {
  github: GitBranch,
  npm: Package,
  paste: ClipboardPaste,
};

export function SourceChip({ scan }: { scan: ScanResult }) {
  const Icon = SOURCE_ICON[scan.server.sourceType] ?? GitBranch;
  const ref = scan.request?.ref;
  return (
    <span
      title={ref ? `${scan.server.sourceType} · ${scan.server.sourceRef} @ ${ref}` : `${scan.server.sourceType} · ${scan.server.sourceRef}`}
      className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-surface-2 px-2 py-1 text-[11px] font-medium text-muted"
    >
      <Icon size={12} className="text-brand" aria-hidden />
      <span className="uppercase tracking-wide">{scan.server.sourceType}</span>
      <span aria-hidden className="text-muted">
        ·
      </span>
      <span className="truncate font-mono text-foreground">
        {scan.server.sourceRef}
        {ref ? <span className="text-muted">@{ref}</span> : null}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Header meta item — icon + short text (created / duration / id).     */
/* ------------------------------------------------------------------ */
export function MetaItem({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <Icon size={13} className="text-muted" aria-hidden />
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* "Demo data" chip — shown when rendering the bundled fixture.        */
/* ------------------------------------------------------------------ */
export function DemoChip({ reason }: { reason: string }) {
  return (
    <span
      title={reason}
      className="inline-flex items-center gap-1 rounded-md border border-caution-border bg-caution-subtle px-2 py-0.5 text-[11px] font-medium text-caution"
    >
      demo data
    </span>
  );
}
