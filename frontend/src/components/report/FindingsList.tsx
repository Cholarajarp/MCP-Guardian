"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ListChecks, Wrench } from "lucide-react";
import type { Finding, Severity } from "@/lib/types";
import { SEVERITY_META, SEVERITY_ORDER, cx } from "./severity";
import { SectionLabel, SeverityBadge } from "./shared";

const CARD_VARIANTS = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const } },
};

export function FindingsList({ findings }: { findings: Finding[] }) {
  const sorted = useMemo(
    () => [...findings].sort((a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity]),
    [findings],
  );

  const counts = useMemo(() => {
    const map = new Map<Severity, number>();
    for (const f of sorted) map.set(f.severity, (map.get(f.severity) ?? 0) + 1);
    return [...map.entries()];
  }, [sorted]);

  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <SectionLabel icon={ListChecks} right={
        <div className="flex flex-wrap items-center gap-1.5">
          {counts.map(([severity, count]) => (
            <span
              key={severity}
              className={cx(
                "rounded-md border px-1.5 py-0.5 text-[10.5px] font-semibold",
                SEVERITY_META[severity].soft,
              )}
            >
              {count} {SEVERITY_META[severity].label.toLowerCase()}
            </span>
          ))}
        </div>
      }>
        Security findings
        <span className="ml-1 rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] font-medium normal-case tracking-normal text-muted">
          {sorted.length}
        </span>
      </SectionLabel>

      {sorted.length === 0 ? (
        <p className="mt-4 rounded-lg border border-positive-border bg-positive-subtle px-4 py-3 text-sm text-positive">
          No findings — no rule matched this server.
        </p>
      ) : (
        <motion.div
          className="mt-4 space-y-2.5"
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.07, delayChildren: 0.15 } } }}
        >
          {sorted.map((finding) => (
            <FindingRow key={finding.id} finding={finding} />
          ))}
        </motion.div>
      )}
    </section>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const meta = SEVERITY_META[finding.severity];

  return (
    <motion.article
      variants={CARD_VARIANTS}
      className={cx(
        "relative overflow-hidden rounded-lg border border-border bg-surface transition-colors",
        open ? "bg-surface-2" : "hover:bg-surface-2",
      )}
    >
      <div aria-hidden className={cx("absolute inset-y-0 left-0 w-[3px]", meta.accent)} />

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 py-3.5 pl-5 pr-4 text-left"
      >
        <SeverityBadge severity={finding.severity} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14.5px] font-medium text-foreground">
            {finding.title}
          </span>
          <span className="mt-0.5 block font-mono text-[11.5px] text-muted">{finding.ruleId}</span>
        </span>
        {finding.file ? (
          <span className="hidden shrink-0 font-mono text-[11.5px] text-muted sm:block">
            {finding.file}
            {finding.line !== undefined ? `:${finding.line}` : ""}
          </span>
        ) : null}
        <ChevronDown
          size={16}
          className={cx(
            "shrink-0 text-muted transition-transform duration-200",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t border-border px-5 pb-4 pt-3.5">
              <p className="text-sm leading-6 text-secondary">{finding.description}</p>

              <div className="rounded-lg border border-positive-border bg-positive-subtle p-3">
                <div className="flex items-start gap-2.5">
                  <Wrench size={14} className="mt-0.5 shrink-0 text-positive" aria-hidden />
                  <div>
                    <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-positive">
                      Remediation
                    </p>
                    <p className="mt-1 text-sm leading-6 text-secondary">{finding.remediation}</p>
                  </div>
                </div>
              </div>

              {finding.evidence ? (
                <div>
                  <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Evidence
                  </p>
                  <pre className="mt-1.5 overflow-x-auto rounded-lg border border-border bg-surface-2 px-3.5 py-2.5 font-mono text-[12.5px] leading-6 text-foreground">
                    {finding.evidence}
                  </pre>
                </div>
              ) : null}

              {finding.file ? (
                <p className="font-mono text-[11.5px] text-muted sm:hidden">
                  {finding.file}
                  {finding.line !== undefined ? `:${finding.line}` : ""}
                </p>
              ) : null}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.article>
  );
}
