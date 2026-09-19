import { FileCheck, Gauge, ListTree, MessageSquareWarning, SearchCode, Sparkles } from "lucide-react";
import { Reveal } from "./Reveal";

/* Same `gap-px` hairline grid as HowItWorks. Children paint opaque backgrounds
   over the --hairline backdrop, so no child carries a border or a radius. */

const FEATURES = [
  {
    icon: SearchCode,
    tag: "No execution",
    title: "Static analysis",
    body: "Tool signatures, manifests and descriptions parsed with 17 rules. The server never runs a single line.",
  },
  {
    icon: Gauge,
    tag: "One number",
    title: "Risk score",
    body: "Severity, blast radius and egress roll into a single 0-100 score you can gate an agent's connection on.",
  },
  {
    icon: ListTree,
    tag: "Full map",
    title: "Tool inventory",
    body: "Every tool, resource and annotation the server exposes — including readOnly and destructive hints.",
  },
  {
    icon: MessageSquareWarning,
    tag: "Model-facing text",
    title: "Prompt injection",
    body: "Tool descriptions reach your model. Guardian flags injected instructions before your agent ever reads them.",
  },
  {
    icon: FileCheck,
    tag: "Enforceable",
    title: "Cedar policy",
    body: "A least-privilege AWS Cedar policy generated from the findings, ready for Verified Permissions or AgentCore.",
  },
  {
    icon: Sparkles,
    tag: "Bedrock Nova",
    title: "Risk narrative",
    body: "Plain-English explanation of what the server can do and why it scored that way. Falls back to a deterministic template.",
  },
];

export function Features() {
  return (
    <section className="border-t border-border bg-background px-8 py-24 md:px-16 lg:px-24 lg:py-28">
      <Reveal>
        <p className="eyebrow-faint mb-5">Capabilities</p>
        <h2 className="display-section text-foreground">
          Trust it
          <br />
          <span className="text-outline">before you trust it.</span>
        </h2>
        <p className="mt-6 max-w-2xl text-xl text-secondary">
          Six things Guardian tells you about a server, every one of them
          derived without executing it.
        </p>
      </Reveal>

      <div className="hairline-grid mt-16 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, i) => {
          const Icon = feature.icon;
          return (
            <div key={feature.title} className="bg-background">
              <Reveal delay={(i % 3) * 0.1} className="h-full">
                <div className="group h-full bg-background p-10 transition-colors hover:bg-surface-2">
                  <div className="mb-6 flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center border border-border-strong">
                      <Icon className="h-4 w-4 text-secondary" aria-hidden="true" />
                    </span>
                    <span className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-muted">
                      {feature.tag}
                    </span>
                  </div>
                  <h3 className="mb-3 text-[1.35rem] font-black uppercase leading-tight tracking-tight text-foreground">
                    {feature.title}
                  </h3>
                  <p className="text-[0.88rem] leading-relaxed text-secondary">{feature.body}</p>
                </div>
              </Reveal>
            </div>
          );
        })}
      </div>
    </section>
  );
}
