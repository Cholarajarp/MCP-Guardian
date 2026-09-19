"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, FileDown, Info, Lock } from "lucide-react";
import { cx } from "./severity";
import { SectionLabel } from "./shared";

const CEDAR_KEYWORDS = new Set([
  "permit",
  "forbid",
  "when",
  "unless",
  "namespace",
  "action",
  "principal",
  "resource",
  "context",
  "in",
  "has",
  "true",
  "false",
  "if",
  "like",
]);

/** Minimal, deterministic Cedar syntax highlight (comments / strings / keywords). */
function highlightLine(line: string): React.ReactNode {
  if (/^\s*\/\//.test(line)) {
    return <span className="italic text-muted">{line}</span>;
  }
  const byString = line.split(/("[^"]*")/g);
  return byString.map((part, i) => {
    if (part.startsWith('"')) {
      return (
        <span key={i} className="text-code-string">
          {part}
        </span>
      );
    }
    const byKeyword = part.split(/\b(permit|forbid|when|unless|namespace|action|principal|resource|context|in|has|true|false|if|like)\b/g);
    return byKeyword.map((tok, j) =>
      CEDAR_KEYWORDS.has(tok) ? (
        <span key={`${i}-${j}`} className="font-semibold text-code-keyword">
          {tok}
        </span>
      ) : (
        tok
      ),
    );
  });
}

export function CedarPolicyCard({ policy, serverName }: { policy: string; serverName: string }) {
  const [copied, setCopied] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lines = useMemo(() => policy.replace(/\t/g, "    ").split("\n"), [policy]);

  useEffect(() => {
    return () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    };
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(policy);
    } catch {
      // Clipboard API unavailable (e.g. non-secure context) — textarea fallback.
      const ta = document.createElement("textarea");
      ta.value = policy;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setCopied(true);
    if (copyTimer.current) clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    const blob = new Blob([policy], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(serverName || "mcp-server").replace(/[^a-zA-Z0-9._-]+/g, "-")}.cedar`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <SectionLabel
        icon={Lock}
        right={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={copy}
              className={cx(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                copied
                  ? "border-positive-border bg-positive-subtle text-positive"
                  : "border-border bg-surface text-foreground hover:bg-surface-2",
              )}
            >
              {copied ? <Check size={13} aria-hidden /> : <Copy size={13} aria-hidden />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={download}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-surface-2"
            >
              <FileDown size={13} aria-hidden />
              Download .cedar
            </button>
          </div>
        }
      >
        Generated AWS Cedar policy
      </SectionLabel>

      <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-surface-2">
        <pre className="min-w-max px-0 py-3 font-mono text-[12.5px] leading-6">
          {lines.map((line, i) => (
            <div key={i} className="flex">
              <span
                aria-hidden
                className="w-10 shrink-0 select-none pr-3 text-right text-[11px] leading-6 text-muted"
              >
                {i + 1}
              </span>
              <code className="whitespace-pre pr-5 text-foreground">{highlightLine(line)}</code>
            </div>
          ))}
        </pre>
      </div>

      <p className="mt-3 flex items-start gap-2 text-[13px] leading-5 text-muted">
        <Info size={14} className="mt-0.5 shrink-0" aria-hidden />
        Paste into AWS Verified Permissions to gate this server&apos;s tools.
      </p>
    </section>
  );
}
