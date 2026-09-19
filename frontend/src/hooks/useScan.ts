"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getScan, startScan } from "../lib/api";
import type { ScanRequest, ScanResult } from "../lib/types";

export type ScanPhase = "idle" | "starting" | "scanning" | "complete" | "error";

export interface ScanState {
  phase: ScanPhase;
  scanId: string | null;
  result: ScanResult | null;
}

const POLL_INTERVAL_MS = 800;
/** Tolerate transient backend hiccups before giving up on a running scan. */
const MAX_CONSECUTIVE_POLL_FAILURES = 5;

/**
 * Drives the scan lifecycle: POST the request, then poll getScan every
 * 800ms until the scan reaches a terminal status (complete | error).
 * All timers are torn down and in-flight responses ignored on unmount.
 */
export function useScan() {
  const [state, setState] = useState<ScanState>({ phase: "idle", scanId: null, result: null });
  const [error, setError] = useState<string | null>(null);

  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveFailures = useRef(0);
  const disposed = useRef(false);

  const clearPollTimer = useCallback(() => {
    if (pollTimer.current !== null) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  useEffect(() => {
    disposed.current = false;
    return () => {
      disposed.current = true;
      clearPollTimer();
    };
  }, [clearPollTimer]);

  const poll = useCallback(
    async (id: string) => {
      try {
        const result = await getScan(id);
        if (disposed.current) return;
        consecutiveFailures.current = 0;
        if (result.status === "complete" || result.status === "error") {
          clearPollTimer();
          if (result.status === "complete") {
            setState({ phase: "complete", scanId: id, result });
          } else {
            setState({ phase: "error", scanId: id, result });
            setError(result.error ?? "The scan failed while analyzing this source.");
          }
        }
      } catch {
        if (disposed.current) return;
        consecutiveFailures.current += 1;
        if (consecutiveFailures.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
          clearPollTimer();
          setState({ phase: "error", scanId: id, result: null });
          setError("Lost contact with the scanner while waiting for results.");
        }
      }
    },
    [clearPollTimer],
  );

  const start = useCallback(
    async (request: ScanRequest) => {
      clearPollTimer();
      consecutiveFailures.current = 0;
      setError(null);
      setState({ phase: "starting", scanId: null, result: null });
      try {
        const { id } = await startScan(request);
        if (disposed.current) return;
        setState({ phase: "scanning", scanId: id, result: null });
        pollTimer.current = setInterval(() => {
          void poll(id);
        }, POLL_INTERVAL_MS);
      } catch (err) {
        if (disposed.current) return;
        setState({ phase: "error", scanId: null, result: null });
        setError(
          err instanceof Error
            ? err.message
            : "Could not reach the scanner. Make sure the backend is running.",
        );
      }
    },
    [clearPollTimer, poll],
  );

  const reset = useCallback(() => {
    clearPollTimer();
    setError(null);
    setState({ phase: "idle", scanId: null, result: null });
  }, [clearPollTimer]);

  return { state, start, reset, error };
}
