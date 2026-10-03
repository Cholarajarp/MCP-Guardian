import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { EXTERNAL_LINK, REPO_URL } from "@/lib/site";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      {/* Same full-bleed scale as the sections above (reference footer is
          px-8 md:px-16), so the columns line up with the page grid. */}
      <div className="px-8 pb-10 pt-16 md:px-16 lg:px-24">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
              <span className="font-display text-sm font-bold text-foreground">MCP Guardian</span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-secondary">
              Static security analysis, risk scoring, and Cedar policy generation for Model
              Context Protocol servers — zero execution, by design.
            </p>
          </div>

          <div className="flex gap-14">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Product</p>
              <ul className="mt-3 space-y-2 text-sm">
                <li>
                  <Link href="/scan" className="text-secondary transition-colors hover:text-foreground">
                    Scan a server
                  </Link>
                </li>
                <li>
                  <Link href="/scan#paste" className="text-secondary transition-colors hover:text-foreground">
                    Paste a config
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Project</p>
              <ul className="mt-3 space-y-2 text-sm">
                <li>
                  <a
                    href={REPO_URL}
                    {...EXTERNAL_LINK}
                    className="text-secondary transition-colors hover:text-foreground"
                  >
                    GitHub
                  </a>
                </li>
                <li>
                  <span className="text-muted">AWS Bedrock + Cedar</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-10 border-t border-border pt-6">
          <p className="text-xs text-muted">
            MCP Guardian.
          </p>
        </div>
      </div>
    </footer>
  );
}
