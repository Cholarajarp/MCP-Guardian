"use client";

import { motion } from "framer-motion";
import { RotateCcw, SquarePen, TriangleAlert } from "lucide-react";

interface ScanErrorProps {
  message: string;
  canRetry: boolean;
  onRetry: () => void;
  onReset: () => void;
}

/** Solid error card — message plus retry. */
export function ScanError({ message, canRetry, onRetry, onReset }: ScanErrorProps) {
  return (
    <motion.section
      role="alert"
      aria-label="Scan error"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mt-6 rounded-2xl border border-critical bg-surface p-4 shadow-sm sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-critical text-critical">
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-base font-semibold text-foreground">Scan failed</h2>
          <p className="mt-1 break-words text-sm text-muted">{message}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {canRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-brand-contrast transition-colors hover:bg-brand-hover"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Try again
              </button>
            )}
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-surface-2"
            >
              <SquarePen className="h-4 w-4" aria-hidden="true" />
              Edit scan
            </button>
          </div>
        </div>
      </div>
    </motion.section>
  );
}
