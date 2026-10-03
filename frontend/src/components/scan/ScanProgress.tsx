"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Check, Loader2, Radar, ShieldCheck } from "lucide-react";
import type { SourceType } from "../../lib/types";

const STEPS = ["Fetching source", "Static analysis", "Risk scoring", "Cedar policy"];

interface ScanProgressProps {
  phase: "starting" | "scanning" | "complete";
  sourceType: SourceType;
  source: string;
  scanId: string | null;
  startedAt: number;
  durationMs?: number | null;
}

function formatElapsed(ms: number): string {
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

/** Indeterminate but polished progress panel with elapsed time. */
export function ScanProgress({ phase, sourceType, source, scanId, startedAt, durationMs }: ScanProgressProps) {
  const reduceMotion = useReducedMotion();
  const [step, setStep] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const complete = phase === "complete";

  // Walk through the steps on a timer; the backend reports a single final result.
  useEffect(() => {
    if (complete) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2200);
    return () => clearInterval(t);
  }, [complete]);

  useEffect(() => {
    if (complete) return;
    const t = setInterval(() => setElapsedMs(Date.now() - startedAt), 100);
    return () => clearInterval(t);
  }, [complete, startedAt]);

  const current = complete ? STEPS.length - 1 : step;
  const elapsed = complete && durationMs != null ? durationMs : elapsedMs;

  return (
    <motion.section
      aria-label="Scan progress"
      aria-live="polite"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mt-6 overflow-hidden rounded-2xl border border-border bg-surface shadow-sm"
    >
      <div aria-hidden="true" className="h-1 w-full bg-surface-2">
        {complete ? (
          <div className="h-full w-full bg-brand" />
        ) : (
          <motion.div
            className="h-full w-1/3 rounded-full bg-brand"
            initial={{ x: "-110%" }}
            animate={reduceMotion ? undefined : { x: "330%" }}
            transition={{ repeat: Infinity, duration: 1.3, ease: "easeInOut" }}
          />
        )}
      </div>

      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2.5">
            {complete ? (
              <ShieldCheck className="h-5 w-5 shrink-0 text-brand" aria-hidden="true" />
            ) : (
              <Radar className="h-5 w-5 shrink-0 animate-pulse text-brand" aria-hidden="true" />
            )}
            <p className="min-w-0 truncate font-display text-base font-semibold text-foreground">
              {complete ? "Analysis complete" : "Scanning"}{" "}
              <span className="font-mono text-sm font-normal text-muted">
                {sourceType}:{source}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm tabular-nums text-muted">{formatElapsed(elapsed)}</span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                complete ? "border-brand text-brand-text" : "border-border text-muted"
              }`}
            >
              {complete ? (
                "Report ready"
              ) : (
                <>
                  <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
                  In progress
                </>
              )}
            </span>
          </div>
        </div>

        <ol className="mt-5">
          {STEPS.map((label, i) => {
            const done = complete || i < current;
            const active = !complete && i === current;
            return (
              <li key={label} className="relative flex gap-3 pb-5 last:pb-0">
                {i < STEPS.length - 1 && (
                  <span
                    aria-hidden="true"
                    className={`absolute left-[11px] top-7 h-[calc(100%-28px)] w-px ${done ? "bg-brand" : "bg-border"}`}
                  />
                )}
                <span
                  aria-hidden="true"
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${
                    done
                      ? "border-brand bg-brand text-brand-contrast"
                      : active
                        ? "border-brand text-brand-text"
                        : "border-border text-muted"
                  }`}
                >
                  {done ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : active ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  )}
                </span>
                <span className={`text-sm leading-6 ${done || active ? "text-foreground" : "text-muted"}`}>
                  {label}
                  {active && i === STEPS.length - 1 && !complete ? "…" : ""}
                </span>
              </li>
            );
          })}
        </ol>

        <p className="mt-4 border-t border-border pt-3 text-xs text-muted">
          {complete ? (
            <>Opening the report{scanId ? ` for ${scanId.slice(0, 12)}` : ""}…</>
          ) : (
            <>
              {scanId ? (
                <>
                  Scan <span className="font-mono">{scanId.slice(0, 12)}</span> ·{" "}
                </>
              ) : (
                "Submitting scan… "
              )}
              You will be taken to the report automatically.
            </>
          )}
        </p>
      </div>
    </motion.section>
  );
}
