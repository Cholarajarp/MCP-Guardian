"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import type { PolicyDecision, ToolInfo } from "@/lib/types";

/**
 * Enforcement preview — the interactive proof that the generated Cedar policy
 * actually gates tools. Toggle simulates `context.approved`; each row shows the
 * decision an AWS Verified Permissions call would return for that tool.
 */

function deriveDecisions(tools: ToolInfo[]): PolicyDecision[] {
  return tools.map((tool) =>
    tool.risks.length === 0
      ? { tool: tool.name, effect: "allow", reason: "No risk signals — permit policy." }
      : {
          tool: tool.name,
          effect: "require-approval",
          reason: `Flagged: ${tool.risks.join(", ")}; forbid until context.approved == true.`,
        },
  );
}

type ChipState = "permit" | "denied" | "approved";

function chipFor(effect: PolicyDecision["effect"], approved: boolean): ChipState {
  if (effect === "allow") return "permit";
  return approved ? "approved" : "denied";
}

const CHIP_META: Record<ChipState, { label: string; className: string; line: string }> = {
  permit: {
    label: "PERMIT",
    className: "bg-[var(--severity-low-subtle)] text-low",
    line: "call allowed",
  },
  denied: {
    label: "DENIED",
    className: "bg-[var(--severity-critical-subtle)] text-critical",
    line: "blocked by forbid policy",
  },
  approved: {
    label: "APPROVED",
    className: "bg-[var(--brand-subtle)] text-brand-text",
    line: "forbid lifted by human approval",
  },
};

export function PolicyPlayground({
  decisions,
  tools,
}: {
  decisions: PolicyDecision[];
  tools: ToolInfo[];
}) {
  const [approved, setApproved] = useState(false);
  const rows = useMemo(
    () => (decisions.length > 0 ? decisions : deriveDecisions(tools)),
    [decisions, tools],
  );

  if (rows.length === 0) return null;

  const blocked = rows.filter((row) => chipFor(row.effect, false) === "denied").length;

  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            <ShieldCheck size={14} className="text-brand" aria-hidden />
            Enforcement preview
          </p>
          <h2 className="mt-2 font-display text-lg font-semibold tracking-tight text-foreground">
            What happens when an agent calls these tools
          </h2>
          <p className="mt-1 max-w-xl text-sm leading-6 text-muted">
            Each row is the decision the generated Cedar policy returns. Turn on human approval to
            lift the <span className="font-mono text-xs">forbid</span> rules — the same
            human-in-the-loop gate you would run in AWS Verified Permissions.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2">
          <div className="text-right">
            <p className="font-mono text-xs text-foreground">
              context.approved = {approved ? "true" : "false"}
            </p>
            <p className="text-[11px] text-muted">Simulate human approval</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={approved}
            aria-label="Simulate human approval (context.approved)"
            onClick={() => setApproved((value) => !value)}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors ${
              approved ? "border-brand bg-brand" : "border-border bg-surface"
            }`}
          >
            <span
              aria-hidden
              className={`inline-block h-4 w-4 rounded-full transition-transform ${
                approved ? "translate-x-[24px]" : "translate-x-[3px]"
              }`}
              style={{ backgroundColor: approved ? "var(--brand-contrast)" : "var(--muted)" }}
            />
          </button>
        </div>
      </div>

      <ul className="mt-5 divide-y divide-[var(--border)] border-y border-border">
        {rows.map((row) => {
          const chip = chipFor(row.effect, approved);
          const meta = CHIP_META[chip];
          return (
            <li
              key={row.tool}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3"
            >
              <div className="min-w-0">
                <p className="font-mono text-sm font-medium text-foreground">
                  invoke(&quot;{row.tool}&quot;)
                </p>
                <p className="mt-0.5 text-xs leading-5 text-muted">{row.reason}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="hidden text-xs text-muted sm:inline">{meta.line}</span>
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={chip}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className={`inline-flex items-center rounded-md px-2 py-1 text-[11px] font-bold tracking-wide ${meta.className}`}
                  >
                    {meta.label}
                  </motion.span>
                </AnimatePresence>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-3 text-xs leading-5 text-muted">
        {blocked > 0
          ? `${blocked} of ${rows.length} tools are blocked until a human approves — exactly what the forbid policies enforce in AWS Verified Permissions.`
          : "Every tool is permitted by the generated policy — no approval gate required for this server."}
      </p>
    </section>
  );
}
