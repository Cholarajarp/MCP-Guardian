import { FileTerminal, Scale, ScanSearch } from "lucide-react";
import { Reveal } from "./Reveal";

/* Reference device: `gap-px` over a --hairline backdrop. The dividers ARE the
   gap; each child paints an opaque background over it. That is why these cards
   carry no border and no radius. */

const STEPS = [
  {
    n: "01",
    icon: ScanSearch,
    title: "Point at a server",
    body: "Paste a server config or point at an MCP repo. The manifest, tool definitions and descriptions are collected. Nothing is executed.",
  },
  {
    n: "02",
    icon: FileTerminal,
    title: "Static analysis",
    body: "17 rules run over the definitions — prompt-injected descriptions, unrestricted writes, silent egress — rolled into one 0-100 risk score.",
  },
  {
    n: "03",
    icon: Scale,
    title: "Cedar policy",
    body: "A least-privilege AWS Cedar policy generated from the findings, beside a plain-English Bedrock narrative. Enforce it, or walk away.",
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="scroll-mt-20 border-t border-border bg-background px-8 py-24 md:px-16 lg:px-24 lg:py-28"
    >
      <Reveal>
        <p className="eyebrow-faint mb-5">How it works</p>
        {/* No max-width on the display heading: at clamp()'s 6rem ceiling the
            second line is wider than max-w-4xl, so capping it forced a wrap
            the hard <br /> had already placed. */}
        <h2 className="display-section text-foreground">
          Unknown server
          <br />
          <span className="text-outline">to enforced policy.</span>
        </h2>
        <p className="mt-6 max-w-2xl text-xl text-secondary">
          Three steps, no execution. The server never runs a single line of its
          own code.
        </p>
      </Reveal>

      <ol className="hairline-grid mt-16 sm:grid-cols-2 lg:grid-cols-3">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          return (
            <li key={step.n} className="bg-background">
              <Reveal delay={i * 0.1} className="h-full">
                <div className="group h-full bg-background p-10 transition-colors hover:bg-surface-2">
                  <div className="mb-6 flex items-center justify-between">
                    <span className="flex h-9 w-9 items-center justify-center border border-border-strong">
                      <Icon className="h-4 w-4 text-secondary" aria-hidden="true" />
                    </span>
                    <span className="font-mono text-4xl font-black tracking-tighter text-muted">
                      {step.n}
                    </span>
                  </div>
                  <h3 className="mb-3 text-[1.35rem] font-black uppercase leading-tight tracking-tight text-foreground">
                    {step.title}
                  </h3>
                  <p className="text-[0.88rem] leading-relaxed text-secondary">{step.body}</p>
                </div>
              </Reveal>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
