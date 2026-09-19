"use client";

import { ArrowUpRight, ScanSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { EXTERNAL_LINK, REPO_URL } from "@/lib/site";

/* Reference nav: full-bleed px-8 md:px-16 lg:px-24 (no centering wrapper, so
   the logo lines up with the section content below it), translucent over a
   20px backdrop blur, turning near-opaque with a hairline bottom border once
   scrolled.

   Deviation: the reference nav is `fixed` and its hero compensates with pt-20.
   This one stays `sticky`, so it keeps occupying flow space -- /scan and
   /report/[id] render under the same Navbar and would need their own top
   padding if it started floating. Same visual treatment, no per-route fixups. */

const LINKS = [
  { href: "/scan", label: "Scan", external: false },
  { href: REPO_URL, label: "GitHub", external: true },
] as const;

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    // Read once on mount too: a restored scroll position (or a deep link to an
    // anchor) can land the page mid-document before any scroll event fires.
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className="sticky top-0 z-50 transition-colors duration-300"
      style={{
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        background: scrolled ? "var(--nav-bg-scrolled)" : "var(--nav-bg)",
        borderBottom: `1px solid ${scrolled ? "var(--border)" : "transparent"}`,
      }}
    >
      <nav className="flex items-center justify-between gap-3 px-5 py-3 sm:px-8 md:px-16 md:py-4 lg:px-24">
        {/* shrink-0 + nowrap: at 380px the wordmark was wrapping mid-flex and
            pushing the nav to 90px tall. */}
        <Link href="/" className="group flex shrink-0 items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-border-strong transition-colors group-hover:border-brand">
            <ShieldCheck className="h-4 w-4 text-brand" aria-hidden="true" />
          </span>
          <span className="whitespace-nowrap text-base font-black tracking-tighter text-foreground sm:text-lg">
            MCP Guardian
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-4 md:gap-10">
          <ul className="hidden list-none items-center gap-8 md:flex lg:gap-10">
            {LINKS.map((link) =>
              link.external ? (
                <li key={link.label}>
                  <a
                    href={link.href}
                    {...EXTERNAL_LINK}
                    className="inline-flex items-center gap-1 text-[0.78rem] font-semibold uppercase tracking-widest text-secondary transition-colors hover:text-foreground"
                    aria-label="MCP Guardian on GitHub (opens in a new tab)"
                  >
                    {link.label}
                    <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                  </a>
                </li>
              ) : (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-[0.78rem] font-semibold uppercase tracking-widest text-secondary transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ),
            )}
          </ul>

          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            {/* "Scan" on phones, "Run a scan" from sm up: the full label plus
                the wordmark and toggle overran 380px. The icon stays either
                way, and the accessible name is always the full phrase. */}
            <Link
              href="/scan"
              aria-label="Run a scan"
              className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap bg-brand px-3.5 py-2 text-[0.7rem] font-black uppercase tracking-widest text-brand-contrast transition-colors hover:bg-brand-hover sm:px-5 sm:py-2.5 sm:text-[0.78rem]"
            >
              <ScanSearch className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="sm:hidden">Scan</span>
              <span className="hidden sm:inline">Run a scan</span>
            </Link>
          </div>
        </div>
      </nav>
    </header>
  );
}
