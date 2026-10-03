"use client";

import { useRef } from "react";
import { FileText, GitBranch, Package } from "lucide-react";
import type { SourceType } from "../../lib/types";
import type { ComponentType } from "react";

const TABS: { value: SourceType; label: string; hint: string; icon: ComponentType<{ className?: string }> }[] = [
  { value: "github", label: "GitHub", hint: "owner/repo or a github.com URL", icon: GitBranch },
  { value: "npm", label: "npm", hint: "a published package name", icon: Package },
  { value: "paste", label: "Paste files", hint: "paste code directly — works offline", icon: FileText },
];

interface SourceTabsProps {
  value: SourceType;
  onChange: (value: SourceType) => void;
  disabled?: boolean;
}

/** Roving-tabindex tab list: ArrowLeft/ArrowRight/Home/End are all supported. */
export function SourceTabs({ value, onChange, disabled = false }: SourceTabsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (to: number) => {
    const next = (to + TABS.length) % TABS.length;
    onChange(TABS[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label="Scan source"
      className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-surface-2 p-1"
      onKeyDown={(e) => {
        if (disabled) return;
        const index = TABS.findIndex((t) => t.value === value);
        if (e.key === "ArrowRight") {
          e.preventDefault();
          move(index + 1);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          move(index - 1);
        } else if (e.key === "Home") {
          e.preventDefault();
          move(0);
        } else if (e.key === "End") {
          e.preventDefault();
          move(TABS.length - 1);
        }
      }}
    >
      {TABS.map((tab, index) => {
        const selected = tab.value === value;
        const Icon = tab.icon;
        return (
          <button
            key={tab.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            id={`scan-tab-${tab.value}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`scan-panel-${tab.value}`}
            tabIndex={selected ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(tab.value)}
            title={tab.hint}
            className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              selected
                ? "bg-surface text-foreground shadow-sm"
                : "text-muted hover:bg-surface hover:text-foreground"
            } disabled:cursor-not-allowed disabled:opacity-60`}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="truncate">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}
