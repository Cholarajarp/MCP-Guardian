"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, History } from "lucide-react";
import { listScans } from "../../lib/api";
import type { ScanResult } from "../../lib/types";
import { RiskBadge } from "./RiskBadge";

function relativeTime(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/**
 * Recent scans strip. Hidden entirely when the history is empty or the
 * backend is unreachable — it is a convenience, never a blocker.
 */
export function HistoryStrip() {
  const [scans, setScans] = useState<ScanResult[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    let cancelled = false;
    listScans(6)
      .then((results) => {
        if (!cancelled) setScans(results.slice(0, 6));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) return null;
  if (scans !== null && scans.length === 0) return null;

  return (
    <section aria-label="Recent scans" className="mt-8">
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
        <History className="h-4 w-4" aria-hidden="true" />
        Recent scans
      </h2>
      <div className="mt-3 rounded-2xl border border-border bg-surface p-2 shadow-sm">
        {scans === null ? (
          <ul aria-hidden="true" className="space-y-1">
            {[0, 1, 2].map((i) => (
              <li key={i} className="h-11 animate-pulse rounded-lg bg-surface-2" />
            ))}
          </ul>
        ) : (
          <ul>
            {scans.map((scan) => (
              <li key={scan.id}>
                <Link
                  href={`/report/${scan.id}`}
                  className="flex items-center gap-3 rounded-lg border border-transparent px-3 py-2.5 transition-colors hover:bg-surface-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {scan.server?.name || scan.request.source}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {scan.request.sourceType} · {scan.server?.sourceRef || scan.request.source}
                    </p>
                  </div>
                  <RiskBadge level={scan.riskLevel} className="shrink-0" />
                  <span className="w-20 shrink-0 text-right text-xs tabular-nums text-muted">
                    {mounted ? relativeTime(scan.createdAt) : ""}
                  </span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
