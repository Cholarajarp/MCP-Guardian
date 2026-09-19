"use client";

import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import type { RiskLevel } from "@/lib/types";
import { RISK_LEVEL_META, cx } from "./severity";

const R = 80;
const CIRC = 2 * Math.PI * R;

/** 60 instrument ticks around the dial; every 5th is longer. Deterministic (SSR-safe). */
const TICKS = Array.from({ length: 60 }, (_, i) => {
  const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
  const r1 = 88;
  const r2 = i % 5 === 0 ? 96 : 92;
  return {
    x1: 100 + r1 * Math.cos(a),
    y1: 100 + r1 * Math.sin(a),
    x2: 100 + r2 * Math.cos(a),
    y2: 100 + r2 * Math.sin(a),
    index: i,
  };
});

export function RiskGauge({ score, level }: { score: number; level: RiskLevel }) {
  const meta = RISK_LEVEL_META[level];
  const clamped = Math.max(0, Math.min(100, score));

  const progress = useMotionValue(0);
  const dashOffset = useTransform(progress, (v) => CIRC * (1 - v / 100));
  const display = useTransform(progress, (v) => Math.round(v).toString());

  useEffect(() => {
    const controls = animate(progress, clamped, {
      duration: 1.4,
      delay: 0.25,
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [progress, clamped]);

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
        <svg viewBox="0 0 200 200" className="h-52 w-52" role="img" aria-label={`Risk score ${clamped} out of 100, ${meta.label}`}>
          {/* instrument ticks */}
          {TICKS.map((t) => {
            const isActive = (t.index / TICKS.length) * 100 <= clamped;
            return (
              <line
                key={t.index}
                x1={t.x1}
                y1={t.y1}
                x2={t.x2}
                y2={t.y2}
                strokeWidth={t.index % 5 === 0 ? 2 : 1}
                className={cx(
                  "transition-colors",
                  isActive
                    ? cx(meta.stroke, "opacity-40")
                    : "stroke-border opacity-70",
                )}
              />
            );
          })}
          {/* track */}
          <circle
            cx="100"
            cy="100"
            r={R}
            fill="none"
            strokeWidth="13"
            className="stroke-surface-2"
          />
          {/* animated progress arc */}
          <motion.circle
            cx="100"
            cy="100"
            r={R}
            fill="none"
            strokeWidth="13"
            strokeLinecap="round"
            className={meta.stroke}
            transform="rotate(-90 100 100)"
            style={{ strokeDasharray: CIRC, strokeDashoffset: dashOffset }}
          />
        </svg>
        {/* center readout */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="flex items-baseline gap-1">
            <motion.span
              className={cx("font-display text-5xl font-bold tabular-nums leading-none", meta.text)}
            >
              {display}
            </motion.span>
            <span className="text-sm font-medium text-muted">/100</span>
          </div>
          <span className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
            Risk score
          </span>
        </div>
      </div>
      <p className="mt-3 text-center text-sm text-muted">{meta.verdict}</p>
    </div>
  );
}
