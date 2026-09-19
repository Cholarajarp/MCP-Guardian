"use client";

import { FilePlus2, Sparkles, Trash2 } from "lucide-react";
import type { PasteRow } from "./pasteExample";
import { exampleRows, nextRowId } from "./pasteExample";

interface PasteEditorProps {
  /** Controlled rows — owned by the form so files survive tab switches. */
  rows: PasteRow[];
  onRowsChange: (rows: PasteRow[]) => void;
  disabled?: boolean;
}

/** File-list editor for the paste tab: rows of [path, content]. */
export function PasteEditor({ rows, onRowsChange, disabled = false }: PasteEditorProps) {
  const addRow = () => onRowsChange([...rows, { id: nextRowId(), path: "", content: "" }]);

  const updateRow = (id: string, patch: Partial<Omit<PasteRow, "id">>) =>
    onRowsChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));

  const removeRow = (id: string) => onRowsChange(rows.filter((row) => row.id !== id));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          Add one row per file. Nothing leaves your machine — the scanner analyzes the pasted code.
        </p>
        <button
          type="button"
          onClick={() => onRowsChange(exampleRows())}
          disabled={disabled}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand px-3 py-1.5 text-xs font-medium text-brand-text transition-colors hover:bg-brand-subtle disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Load example files
        </button>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-surface-2 px-4 py-8 text-center">
          <p className="text-sm font-medium text-foreground">No files yet</p>
          <p className="mt-1 text-sm text-muted">
            Add a file row below, or load the example to see the full flow in seconds.
          </p>
        </div>
      ) : (
        <ol className="space-y-3">
          {rows.map((row, index) => (
            <li key={row.id} className="rounded-lg border border-border bg-surface-2 p-3">
              <div className="flex items-start gap-2">
                <label className="min-w-0 flex-1">
                  <span className="sr-only">{`File ${index + 1} path`}</span>
                  <input
                    type="text"
                    value={row.path}
                    disabled={disabled}
                    onChange={(e) => updateRow(row.id, { path: e.target.value })}
                    placeholder="server.py"
                    className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 font-mono text-sm text-foreground placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => removeRow(row.id)}
                  disabled={disabled}
                  aria-label={`Remove file ${row.path || index + 1}`}
                  className="rounded-md border border-transparent p-1.5 text-muted transition-colors hover:border-border hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <label className="mt-2 block">
                <span className="sr-only">{`File ${index + 1} content`}</span>
                <textarea
                  value={row.content}
                  disabled={disabled}
                  onChange={(e) => updateRow(row.id, { content: e.target.value })}
                  rows={6}
                  spellCheck={false}
                  placeholder="# Paste the file contents here"
                  className="w-full resize-y rounded-md border border-border bg-surface px-2.5 py-2 font-mono text-xs leading-relaxed text-foreground placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-60"
                />
              </label>
            </li>
          ))}
        </ol>
      )}

      <button
        type="button"
        onClick={addRow}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <FilePlus2 className="h-4 w-4" />
        Add file
      </button>
    </div>
  );
}
