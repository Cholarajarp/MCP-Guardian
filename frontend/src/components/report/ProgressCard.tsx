"use client";

import { motion } from "framer-motion";
import { Check, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import type { ScanStatus } from "@/lib/types";
import { cx } from "./severity";

const STEPS = [
  "Queued",
  "Fetching source",
  "Static analysis",
  "AI assessment (Bedrock)",
  "Cedar policy generation",
];

/** Presentational progress estimate while the backend reports pending/scanning. */
function activeStepFor(elapsedSec: number): number {
  return Math.min(Math.floor(elapsedSec / 2.2), STEPS.length - 1);
}

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function ProgressCard({
  status,
  serverName,
  sourceRef,
  elapsedSec,
  stalled,
}: {
  status: ScanStatus;
  serverName: string;
  sourceRef: string;
  elapsedSec: number;
  stalled: boolean;
}) {
  const active = stalled ? STEPS.length - 1 : activeStepFor(elapsedSec);

  return (
    <section className="rounded-xl border border-border bg-surface p-6 shadow-card">
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
        {/* pulsing radar */}
        <div className="relative shrink-0">
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-full border-2 border-brand"
            animate={{ scale: [1, 1.7], opacity: [0.7, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
          />
          <motion.div
            className="flex size-14 items-center justify-center rounded-full bg-[color:var(--brand-subtle)]"
            animate={{ opacity: [1, 0.75, 1] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          >
            <LoaderCircle size={24} className="animate-spin text-brand" aria-hidden />
          </motion.div>
        </div>

        <div className="min-w-0 flex-1 text-center sm:text-left">
          <div className="flex flex-wrap items-baseline justify-center gap-x-3 gap-y-1 sm:justify-start">
            <h2 className="font-display text-lg font-bold tracking-tight text-foreground">
              {status === "pending" ? "Scan queued" : "Scanning"} {serverName || "server"}…
            </h2>
            <span className="font-mono text-xs text-muted">
              {sourceRef}
              {elapsedSec > 0 ? ` · ${formatElapsed(elapsedSec)} elapsed` : ""}
            </span>
          </div>

          <ol className="mt-4 grid gap-2 sm:grid-cols-5 sm:gap-1.5">
            {STEPS.map((step, i) => {
              const done = !stalled && i < active;
              const is = !stalled && i === active;
              return (
                <li
                  key={step}
                  className={cx(
                    "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-[11.5px] font-medium sm:flex-col sm:items-start sm:gap-1.5",
                    done && "border-positive-border bg-positive-subtle text-positive",
                    is && "border-brand bg-[color:var(--brand-subtle)] text-foreground",
                    !done && !is && "border-border bg-surface-2 text-muted",
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    {done ? (
                      <Check size={12} strokeWidth={3} aria-hidden />
                    ) : is ? (
                      <LoaderCircle size={12} className="animate-spin text-brand" aria-hidden />
                    ) : (
                      <span className="size-1.5 rounded-full bg-muted" aria-hidden />
                    )}
                    <span className="font-mono text-[10px] text-muted">{String(i + 1).padStart(2, "0")}</span>
                  </span>
                  <span className="text-left leading-tight">{step}</span>
                </li>
              );
            })}
          </ol>

          {stalled ? (
            <p className="mt-4 inline-flex items-start gap-2 rounded-lg border border-caution-border bg-caution-subtle px-3 py-2 text-left text-[13px] leading-5 text-caution">
              <TriangleAlert size={14} className="mt-0.5 shrink-0" aria-hidden />
              <span>
                Still scanning — refresh the page to check again. Long-running analyses can take a
                few minutes on the backend.
              </span>
            </p>
          ) : (
            <p className="mt-4 inline-flex items-center gap-1.5 text-[12px] text-muted">
              <RefreshCw size={11} className="animate-[spin_2.5s_linear_infinite]" aria-hidden />
              Polling for results every second…
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
