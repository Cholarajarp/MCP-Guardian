"use client";

import { Sparkles } from "lucide-react";
import type { RiskLevel } from "@/lib/types";
import { RISK_LEVEL_META, cx } from "./severity";

/** "AI risk assessment (AWS Bedrock)" — narrative summary with a riskLevel accent bar. */
export function NarrativeCard({ narrative, level }: { narrative: string; level: RiskLevel }) {
  const meta = RISK_LEVEL_META[level];
  return (
    <section className="relative h-full overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <div aria-hidden className={cx("absolute inset-y-0 left-0 w-1", meta.accent)} />
      <div className="flex h-full flex-col p-5 pl-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            <Sparkles size={14} className="text-brand" aria-hidden />
            AI risk assessment
          </span>
          <span className="rounded-md bg-[color:var(--brand-subtle)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-text">
            AWS Bedrock
          </span>
        </div>
        <p className="mt-3 text-[15px] leading-7 text-secondary">{narrative}</p>
      </div>
    </section>
  );
}
