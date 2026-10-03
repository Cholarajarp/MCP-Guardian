"use client";

import { ShieldCheck, Table2 } from "lucide-react";
import type { ToolInfo } from "@/lib/types";
import { cx, riskChipClass } from "./severity";
import { SectionLabel } from "./shared";

export function ToolTable({ tools }: { tools: ToolInfo[] }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <SectionLabel
        icon={Table2}
        right={
          <span className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] font-medium text-muted">
            {tools.length}
          </span>
        }
      >
        Tools &amp; capabilities
      </SectionLabel>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.12em] text-muted">
              <th scope="col" className="py-2 pr-4 font-semibold">Tool</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Description</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Annotations</th>
              <th scope="col" className="py-2 font-semibold">Flagged risks</th>
            </tr>
          </thead>
          <tbody>
            {tools.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-4 text-muted">No tools discovered.</td>
              </tr>
            ) : (
              tools.map((tool) => (
                <tr key={tool.name} className="border-b border-border last:border-0 align-top">
                  <td className="py-3 pr-4 font-mono text-[13px] font-semibold text-foreground">
                    {tool.name}
                  </td>
                  <td className="max-w-[280px] py-3 pr-4 lg:max-w-[360px]">
                    <span className="block truncate text-[13px] text-muted" title={tool.description}>
                      {tool.description || "—"}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    {tool.annotations.length === 0 ? (
                      <span className="text-[13px] text-muted">—</span>
                    ) : (
                      <span className="flex flex-wrap gap-1.5">
                        {tool.annotations.map((a) => (
                          <span
                            key={a}
                            className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted"
                          >
                            {a}
                          </span>
                        ))}
                      </span>
                    )}
                  </td>
                  <td className="py-3">
                    {tool.risks.length === 0 ? (
                      <span className="inline-flex items-center gap-1 rounded-md border border-positive-border bg-positive-subtle px-1.5 py-0.5 text-[11px] font-medium text-positive">
                        <ShieldCheck size={11} aria-hidden /> none flagged
                      </span>
                    ) : (
                      <span className="flex max-w-[280px] flex-wrap gap-1.5">
                        {tool.risks.map((risk) => (
                          <span
                            key={risk}
                            className={cx(
                              "rounded border px-1.5 py-0.5 text-[11px] font-medium",
                              riskChipClass(risk),
                            )}
                          >
                            {risk}
                          </span>
                        ))}
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
