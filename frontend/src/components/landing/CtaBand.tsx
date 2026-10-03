import { ArrowRight, ScanSearch } from "lucide-react";
import Link from "next/link";
import { Reveal } from "./Reveal";

/* Reference CTA band: tight 10px graticule wash, oversized display type with an
   outlined second line, and a square solid button carrying the pulsing ring +
   shine sweep. No card, no radius, no shadow. */

/* The one section that stays centered: the reference's closing CTA is
   `max-w-4xl mx-auto text-center` too. Centering is the exception here, not
   the default. */
export function CtaBand() {
  return (
    <section className="relative overflow-hidden border-t border-border bg-background px-8 py-32 md:px-16 lg:px-24 lg:py-36">
      <div className="bg-graticule pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto max-w-4xl text-center">
        <Reveal>
          <p className="eyebrow-faint mb-8">Free · nothing executes</p>
          <h2 className="display-section text-foreground">
            Scan first.
            <br />
            <span className="text-outline">Connect second.</span>
          </h2>
          <p className="mx-auto mt-8 max-w-xl text-xl leading-relaxed text-secondary">
            Paste a config or point at a repo. Findings, a risk score and an
            enforceable Cedar policy in seconds.
          </p>

          <div className="mt-14 flex justify-center">
            <Link
              href="/scan"
              className="shine pulse-ring group relative inline-flex items-center gap-4 overflow-hidden bg-brand px-14 py-6 text-base font-black uppercase tracking-widest text-brand-contrast transition-colors hover:bg-brand-hover"
            >
              <span className="relative z-10 inline-flex items-center gap-4">
                <ScanSearch className="h-5 w-5" aria-hidden="true" />
                Run a scan
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1.5" aria-hidden="true" />
              </span>
            </Link>
          </div>

          <p className="eyebrow-faint mt-10">Static analysis · 17 rules · Cedar output</p>
        </Reveal>
      </div>
    </section>
  );
}
