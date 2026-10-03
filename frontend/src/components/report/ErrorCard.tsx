"use client";

import Link from "next/link";
import { ArrowRight, RefreshCw, ShieldX } from "lucide-react";

export function ErrorCard({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <section className="rounded-xl border border-critical bg-[color:var(--severity-critical-subtle)] p-6 shadow-card">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface shadow-card">
          <ShieldX size={22} className="text-critical" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-bold tracking-tight text-critical">
            Scan failed
          </h2>
          <p className="mt-1 text-sm leading-6 text-secondary">
            The scanner reported an error for this server. Nothing was blocked — no Cedar policy was
            generated.
          </p>
          {message ? (
            <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-surface px-3.5 py-2.5 font-mono text-[12.5px] leading-6 text-critical">
              {message}
            </pre>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3.5 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-surface-2"
            >
              <RefreshCw size={13} aria-hidden />
              Retry scan lookup
            </button>
            <Link
              href="/scan"
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3.5 py-2 text-xs font-semibold text-brand-contrast transition-colors hover:bg-brand-hover"
            >
              Scan another server
              <ArrowRight size={13} aria-hidden />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
