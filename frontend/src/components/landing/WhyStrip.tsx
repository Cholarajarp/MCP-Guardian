import { TriangleAlert } from "lucide-react";
import { Reveal } from "./Reveal";

/**
 * Thin warning strip — one flat, tinted band. Solid fill (severity-critical
 * token), 1px borders, no blur, no gradient.
 */
export function WhyStrip() {
  return (
    <section
      aria-label="Security warning"
      className="border-b border-border bg-[var(--severity-critical-subtle)]"
    >
      <div className="px-8 py-4 md:px-16 lg:px-24">
        <Reveal y={12}>
          <p className="flex flex-col items-start gap-2 text-sm leading-relaxed text-foreground sm:flex-row sm:items-center sm:gap-3">
            <span className="inline-flex shrink-0 items-center gap-2 font-semibold">
              <TriangleAlert className="h-4 w-4 text-critical" aria-hidden="true" />
              <span className="font-mono text-[11px] font-bold uppercase tracking-[0.16em] text-critical">
                Before you connect
              </span>
            </span>
            <span className="text-secondary">
              MCP servers can hide prompt-injected tool descriptions and destructive tools that
              agents auto-approve.
            </span>
          </p>
        </Reveal>
      </div>
    </section>
  );
}
