"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import type { ScanRequest, SourceType } from "../../lib/types";
import { useScan } from "../../hooks/useScan";
import { HistoryStrip } from "./HistoryStrip";
import { ScanError } from "./ScanError";
import { ScanForm } from "./ScanForm";
import { ScanProgress } from "./ScanProgress";
import { SourceTabs } from "./SourceTabs";

/**
 * Scan flow orchestrator: source tabs + form -> progress panel -> report.
 * Navigation to /report/[id] happens ~0.9s after completion so the success
 * state is visible. This page intentionally renders no navbar — the root
 * layout owns chrome.
 */
export function ScanView() {
  const router = useRouter();
  const { state, start, reset, error } = useScan();

  const [sourceType, setSourceType] = useState<SourceType>("github");
  const [startedAt, setStartedAt] = useState(0);
  const [lastRequest, setLastRequest] = useState<ScanRequest | null>(null);

  const busy = state.phase === "starting" || state.phase === "scanning";

  const handleStart = useCallback(
    (request: ScanRequest) => {
      setLastRequest(request);
      setStartedAt(Date.now());
      void start(request);
    },
    [start],
  );

  const handleRetry = useCallback(() => {
    if (!lastRequest) {
      reset();
      return;
    }
    setStartedAt(Date.now());
    void start(lastRequest);
  }, [lastRequest, reset, start]);

  // Hand off to the report page once the scan completes.
  useEffect(() => {
    if (state.phase !== "complete" || !state.scanId) return;
    const id = state.scanId;
    const timer = setTimeout(() => router.push(`/report/${id}`), 900);
    return () => clearTimeout(timer);
  }, [state.phase, state.scanId, router]);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-10 sm:px-6 sm:pt-14">
      <header>
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-brand-text">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          Static analysis · Cedar policy generation
        </span>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Scan an MCP server
        </h1>
        <p className="mt-2 max-w-2xl text-base text-muted">
          Point at a GitHub repo or an npm package, or paste code directly. MCP Guardian returns
          findings, a risk score, and a ready-to-use Cedar policy — before an agent ever connects.
        </p>
      </header>

      <section
        aria-label="Start a scan"
        className="mt-8 rounded-2xl border border-border bg-surface shadow-sm"
      >
        <div className="border-b border-border p-4 sm:px-5">
          <SourceTabs value={sourceType} onChange={setSourceType} disabled={busy} />
        </div>
        <div className="p-4 sm:p-5">
          <ScanForm sourceType={sourceType} busy={busy} onSubmit={handleStart} />
        </div>
      </section>

      <AnimatePresence mode="wait" initial={false}>
        {state.phase === "error" ? (
          <motion.div
            key="scan-error"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <ScanError
              message={error ?? "The scan failed."}
              canRetry={lastRequest !== null}
              onRetry={handleRetry}
              onReset={reset}
            />
          </motion.div>
        ) : state.phase !== "idle" ? (
          <motion.div
            key="scan-progress"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <ScanProgress
              phase={state.phase === "complete" ? "complete" : state.phase}
              sourceType={lastRequest?.sourceType ?? sourceType}
              source={lastRequest?.source ?? "…"}
              scanId={state.scanId}
              startedAt={startedAt}
              durationMs={state.result?.durationMs ?? null}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <HistoryStrip />
    </main>
  );
}
