"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Download, Fingerprint, Gauge, Clock, Timer } from "lucide-react";
import { getScan } from "@/lib/api";
import type { ScanResult } from "@/lib/types";
import { reportFixture } from "@/mocks/report.fixture";
import { CedarPolicyCard } from "@/components/report/CedarPolicyCard";
import { ErrorCard } from "@/components/report/ErrorCard";
import { FindingsList } from "@/components/report/FindingsList";
import { NarrativeCard } from "@/components/report/NarrativeCard";
import { PolicyPlayground } from "@/components/report/PolicyPlayground";
import { ProgressCard } from "@/components/report/ProgressCard";
import { RiskGauge } from "@/components/report/RiskGauge";
import { ToolTable } from "@/components/report/ToolTable";
import { RISK_LEVEL_META, cx, formatCreated, formatDuration } from "@/components/report/severity";
import {
  DemoChip,
  MetaItem,
  Reveal,
  RiskBadge,
  SectionLabel,
  SourceChip,
  StatusPill,
} from "@/components/report/shared";

const POLL_INTERVAL_MS = 1000;
const POLL_CAP_MS = 60_000;

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [demo, setDemo] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [stalled, setStalled] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // ------------------------------------------------------------------
  // DEMO FALLBACK (clearly marked, one knob): `?mock=1` renders the
  // bundled fixture; if the API is unreachable we also fall back to the
  // fixture so the report page stays demoable with the backend offline.
  // ------------------------------------------------------------------
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("mock")) {
      setScan(reportFixture);
      setDemo(true);
      return;
    }
    setScan(null);
    setDemo(false);
    setStalled(false);
    setElapsedSec(0);
    let cancelled = false;
    getScan(id)
      .then((data) => {
        if (!cancelled) setScan(data);
      })
      .catch(() => {
        if (!cancelled) {
          setScan(reportFixture);
          setDemo(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  // Poll getScan every 1s while pending/scanning; cap at 60s → "still scanning".
  const inFlight = scan?.status === "pending" || scan?.status === "scanning";
  useEffect(() => {
    if (!inFlight) return;
    const started = Date.now();
    const tick = setInterval(
      () => setElapsedSec(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    const poll = setInterval(() => {
      if (Date.now() - started > POLL_CAP_MS) {
        setStalled(true);
        clearInterval(poll);
        return;
      }
      getScan(id)
        .then((next) => setScan(next))
        .catch(() => {
          /* transient backend hiccup — keep polling */
        });
    }, POLL_INTERVAL_MS);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [inFlight, id]);

  const exportJson = useCallback(() => {
    if (!scan) return;
    const blob = new Blob([JSON.stringify(scan, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mcp-guardian-scan-${scan.id || id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [scan, id]);

  const retry = useCallback(() => setReloadKey((k) => k + 1), []);

  /* ------------------------------ loading ------------------------------ */
  if (!scan) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 pb-16 pt-8 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-6" aria-label="Loading report">
          <div className="space-y-3">
            <div className="h-6 w-44 rounded-md bg-surface-2" />
            <div className="h-9 w-72 rounded-md bg-surface-2" />
            <div className="h-4 w-full max-w-md rounded bg-surface-2" />
          </div>
          <div className="grid gap-4 lg:grid-cols-12">
            <div className="h-80 rounded-xl bg-surface-2 lg:col-span-4" />
            <div className="h-80 rounded-xl bg-surface-2 lg:col-span-8" />
          </div>
          <div className="h-64 rounded-xl bg-surface-2" />
        </div>
      </main>
    );
  }

  const complete = scan.status === "complete";
  const riskMeta = RISK_LEVEL_META[scan.riskLevel];
  const duration = formatDuration(scan.durationMs);

  /* ------------------------------ render ------------------------------ */
  return (
    <div className="relative">
      {/* Graph-paper backdrop band — flat 1px grid lines, masked to fade out. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-graph-paper graph-fade"
      />
      <main className="relative mx-auto w-full max-w-6xl px-4 pb-16 pt-8 sm:px-6 lg:px-8">
      {/* 1 ── Header row */}
      <Reveal>
        <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SourceChip scan={scan} />
              {demo ? (
                <DemoChip reason="Backend unreachable or ?mock=1 — showing the bundled demo report." />
              ) : null}
            </div>
            <h1 className="mt-2.5 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              {scan.server.name}
            </h1>
            {scan.server.description ? (
              <p className="mt-1.5 max-w-xl text-sm leading-6 text-muted">
                {scan.server.description}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
              <MetaItem icon={Clock}>{formatCreated(scan.createdAt)}</MetaItem>
              {duration ? <MetaItem icon={Timer}>{duration} scan time</MetaItem> : null}
              <MetaItem icon={Fingerprint}>
                <span className="font-mono">{scan.id.slice(0, 8)}</span>
              </MetaItem>
            </div>
          </div>

          <div className="flex flex-col items-start gap-2.5 sm:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={scan.status} />
              {complete ? <RiskBadge level={scan.riskLevel} /> : null}
            </div>
            {complete ? (
              <div className="flex items-baseline gap-1.5">
                <span
                  className={cx(
                    "font-display text-4xl font-bold tabular-nums leading-none",
                    riskMeta.text,
                  )}
                >
                  {scan.riskScore}
                </span>
                <span className="text-sm font-medium text-muted">/100</span>
              </div>
            ) : null}
          </div>
        </header>
      </Reveal>

      {/* In-flight → progress card that polls until complete/error (60s cap) */}
      {inFlight ? (
        <Reveal delay={0.1} className="mt-6">
          <ProgressCard
            status={scan.status}
            serverName={scan.server.name}
            sourceRef={scan.server.sourceRef}
            elapsedSec={elapsedSec}
            stalled={stalled}
          />
        </Reveal>
      ) : null}

      {/* Error → solid error card with the message */}
      {scan.status === "error" ? (
        <Reveal delay={0.1} className="mt-6">
          <ErrorCard message={scan.error} onRetry={retry} />
        </Reveal>
      ) : null}

      {/* Complete → full report */}
      {complete ? (
        <>
          {/* 2 + 3 ── RiskGauge & narrative */}
          <Reveal delay={0.08} className="mt-6">
            <div className="grid gap-4 lg:grid-cols-12">
              <div className="rounded-xl border border-border bg-surface p-5 shadow-card lg:col-span-4">
                <SectionLabel icon={Gauge}>Risk score</SectionLabel>
                <div className="mt-3">
                  <RiskGauge score={scan.riskScore} level={scan.riskLevel} />
                </div>
              </div>
              <div className="lg:col-span-8">
                <NarrativeCard narrative={scan.narrative} level={scan.riskLevel} />
              </div>
            </div>
          </Reveal>

          {/* 4 ── Findings */}
          <Reveal delay={0.16} className="mt-4">
            <FindingsList findings={scan.findings} />
          </Reveal>

          {/* 5 ── Tools */}
          <Reveal delay={0.22} className="mt-4">
            <ToolTable tools={scan.tools} />
          </Reveal>

          {/* 5b ── Enforcement preview (interactive policy decisions) */}
          <Reveal delay={0.25} className="mt-4">
            <PolicyPlayground decisions={scan.policyDecisions ?? []} tools={scan.tools} />
          </Reveal>

          {/* 6 ── Cedar policy */}
          <Reveal delay={0.28} className="mt-4">
            <CedarPolicyCard policy={scan.cedarPolicy} serverName={scan.server.name} />
          </Reveal>

          {/* 7 ── Actions */}
          <Reveal delay={0.34} className="mt-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-5 py-4 shadow-card">
              <p className="text-sm text-muted">
                Reviewed{" "}
                <span className="font-medium text-foreground">{scan.server.name}</span>? Export the
                raw evidence or scan your next server.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={exportJson}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold text-foreground transition-colors hover:bg-surface-2"
                >
                  <Download size={14} aria-hidden />
                  Export JSON
                </button>
                <Link
                  href="/scan"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-brand-contrast transition-colors hover:bg-brand-hover"
                >
                  Scan another server
                  <ArrowRight size={14} aria-hidden />
                </Link>
              </div>
            </div>
          </Reveal>
        </>
      ) : null}
      </main>
    </div>
  );
}
