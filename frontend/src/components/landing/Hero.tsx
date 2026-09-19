"use client";

import { motion } from "framer-motion";
import { ArrowRight, ScanSearch } from "lucide-react";
import Link from "next/link";

/* Reference anatomy, applied:
   - display type: clamp()-scaled, font-black, UPPERCASE, hard line break,
     second line rendered as an outline (WebkitTextStroke)
   - status pill: 1px square border + pulsing dot + 0.2em tracked micro-label
   - primary CTA: solid fill, square, pulsing ring + shine sweep on hover
   - capability chips: square 1px hairline borders, uppercase micro-type
   - right panel: the reference's mono terminal card (traffic dots, live dot)

   Deviation, on purpose: the reference hero is a single full-bleed column over
   grayscale photography. Here the right column carries the mono report panel
   instead, because the actual scanner output is the thing worth showing in a
   security demo. The vocabulary is the reference's; the content is the product. */

const ease = [0.21, 0.65, 0.36, 1] as const;

const FINDINGS = [
  { severity: "CRITICAL", tool: "fs.write", note: "unrestricted filesystem write", color: "text-critical", bg: "bg-critical" },
  { severity: "HIGH", tool: "shell.exec", note: "command injection surface", color: "text-high", bg: "bg-high" },
  { severity: "MEDIUM", tool: "fetch", note: "unrestricted network egress", color: "text-medium", bg: "bg-medium" },
  { severity: "MEDIUM", tool: "description", note: "\u201Cignore previous instructions\u201D", color: "text-medium", bg: "bg-medium" },
] as const;

const CAPABILITIES = [
  "Static only",
  "17 rules",
  "Risk 0-100",
  "Cedar policy",
  "Prompt injection",
  "Tool inventory",
] as const;

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-border bg-background">
      <div className="bg-graticule pointer-events-none absolute inset-0" aria-hidden="true" />

      {/* Full-bleed, as the reference is: content starts at the padding edge
          (px-8 md:px-16 lg:px-24) with no centering wrapper. A `mx-auto
          max-w-7xl` here parked everything in a middle column and left ~123px
          of dead gutter per side at 1536px. */}
      {/* Top padding is deliberately small: the Navbar is `sticky`, not
          `fixed`, so it already occupies flow space. The reference's pt-20
          exists only because its nav floats over the hero -- copying that
          number here stacked ~100px of dead band under the nav. */}
      <div className="relative px-5 pb-20 pt-10 sm:px-8 md:px-16 lg:px-24 lg:pb-28 lg:pt-14">
        {/* min-w-0 on the grid children: grid items default to
            `min-width: auto`, so the single mobile column could not shrink
            below the mono panel's min-content (~491px) and the hero clipped
            at a 380px viewport under `overflow-hidden`. */}
        <div className="grid items-center gap-14 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16 2xl:gap-24">
          <div className="min-w-0">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.1 }}
              className="inline-flex items-center gap-2.5 border border-border-strong px-4 py-1.5"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden="true" />
              <span className="eyebrow-faint">Static security scanner for MCP</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease }}
              className="display-hero mt-8 text-foreground"
            >
              Scan before
              <br />
              <span className="text-outline-brand">you connect.</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.4, ease }}
              className="mt-8 max-w-xl text-lg leading-relaxed text-secondary"
            >
              MCP Guardian reads a Model Context Protocol server without running
              it — mapping every tool, ranking findings by severity, scoring the
              risk, and generating an AWS Cedar policy you can enforce.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.55, ease }}
              className="mt-10 flex flex-col gap-4 sm:flex-row"
            >
              <Link
                href="/scan"
                className="shine pulse-ring group relative inline-flex w-fit items-center gap-3 overflow-hidden bg-brand px-10 py-5 text-sm font-black uppercase tracking-widest text-brand-contrast transition-colors hover:bg-brand-hover"
              >
                <span className="relative z-10 inline-flex items-center gap-3">
                  <ScanSearch className="h-4 w-4" aria-hidden="true" />
                  Scan a server
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                </span>
              </Link>
              <Link
                href="#how-it-works"
                className="inline-flex w-fit items-center gap-2 border border-border-strong px-10 py-5 text-sm font-bold uppercase tracking-widest text-secondary transition-colors hover:border-brand hover:text-foreground"
              >
                How it works
              </Link>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.75, ease }}
              className="mt-16"
            >
              <p className="eyebrow-faint mb-4">Zero execution · analysis only</p>
              <div className="flex flex-wrap gap-2.5">
                {CAPABILITIES.map((tag, i) => (
                  <motion.span
                    key={tag}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.85 + i * 0.07 }}
                    className="border border-border px-3 py-1.5 text-[0.68rem] font-bold uppercase tracking-widest text-muted"
                  >
                    {tag}
                  </motion.span>
                ))}
              </div>
            </motion.div>
          </div>

          {/* Mono terminal panel — reference device, square, 1px hairline. */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.35, ease }}
            className="min-w-0 border border-border bg-surface p-5 font-mono shadow-card sm:p-8"
          >
            <div className="mb-6 flex items-center gap-2 border-b border-border pb-4">
              <span className="flex gap-1.5" aria-hidden="true">
                <span className="h-3 w-3 rounded-full border border-border bg-surface-2" />
                <span className="h-3 w-3 rounded-full border border-border bg-surface-2" />
                <span className="h-3 w-3 rounded-full border border-border bg-surface-2" />
              </span>
              <span className="ml-2 text-[0.65rem] uppercase tracking-widest text-muted">
                report.json · complete
              </span>
              <span className="ml-auto h-2 w-2 rounded-full bg-positive" aria-hidden="true" />
            </div>

            <div className="space-y-4 text-[13px] leading-relaxed">
              <p className="text-secondary">
                <span className="text-brand-text">$</span> guardian scan server-filesystem
              </p>
              <p className="text-muted">✓ 14 tools · 6 resources · 0 executions</p>

              <div className="flex items-center justify-between border border-border bg-surface-2 px-4 py-3">
                <span className="text-[0.65rem] uppercase tracking-widest text-muted">Risk score</span>
                <span className="text-2xl font-black tracking-tighter text-foreground">
                  72<span className="text-sm font-bold text-muted">/100</span>
                </span>
              </div>

              <ul className="space-y-2.5">
                {FINDINGS.map((f) => (
                  <li key={f.tool + f.note} className="flex items-baseline gap-2.5">
                    <span className={`w-[70px] shrink-0 text-[11px] font-bold ${f.color}`}>
                      [{f.severity}]
                    </span>
                    <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${f.bg}`} aria-hidden="true" />
                    <span className="text-foreground">{f.tool}</span>
                    <span className="truncate text-muted">— {f.note}</span>
                  </li>
                ))}
              </ul>

              <p className="border-t border-border pt-4 text-positive">
                ✓ policy.cedar — 4 allow · 3 require-approval
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
