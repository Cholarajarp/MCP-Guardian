"use client";

import { useEffect, useState } from "react";
import { Loader2, ScanSearch } from "lucide-react";
import type { ScanRequest, SourceType } from "../../lib/types";
import type { PasteRow } from "./pasteExample";
import { rowsToFiles } from "./pasteExample";
import { PasteEditor } from "./PasteEditor";

interface ScanFormProps {
  sourceType: SourceType;
  busy: boolean;
  onSubmit: (request: ScanRequest) => void;
}

const INPUT_CLASS =
  "w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-foreground placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-60";

/** Accepts "owner/repo" or a full github.com URL (optionally /tree/<ref>). */
export function parseGithubInput(value: string): { repo: string; ref: string } | null {
  const input = value.trim();
  if (!input) return null;

  const url =
    input.match(
      /^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/\s#?]+)\/([^/\s#?]+)\/?(?:[?#].*)?$/i,
    ) ?? input.match(/^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/\s#?]+)\/([^/\s#?]+)/i);
  if (url) {
    const repo = `${url[1]}/${url[2].replace(/\.git$/i, "")}`;
    const tree = input.match(/\/tree\/([^/\s#?]+)/i);
    return { repo, ref: tree ? tree[1] : "" };
  }

  const short = input.match(/^([\w.-]+)\/([\w.-]+?)(?:\.git)?$/);
  if (short) return { repo: `${short[1]}/${short[2]}`, ref: "" };

  return null;
}

const NPM_NAME = /^(@[a-z0-9-~][a-z0-9-._~]*\/)?[a-z0-9-~][a-z0-9-._~]*$/i;

export function ScanForm({ sourceType, busy, onSubmit }: ScanFormProps) {
  const [repoInput, setRepoInput] = useState("");
  const [refInput, setRefInput] = useState("");
  const [pkg, setPkg] = useState("");
  // Owned here (not in PasteEditor) so loaded files survive tab switches.
  const [pasteRows, setPasteRows] = useState<PasteRow[]>([]);
  const [fieldError, setFieldError] = useState<string | null>(null);

  useEffect(() => {
    setFieldError(null);
  }, [sourceType]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;

    if (sourceType === "github") {
      const parsed = parseGithubInput(repoInput);
      if (!parsed) {
        setFieldError("Enter a repository as owner/repo or paste a github.com URL.");
        return;
      }
      const ref = refInput.trim() || parsed.ref || undefined;
      setFieldError(null);
      onSubmit({ sourceType: "github", source: parsed.repo, ...(ref ? { ref } : {}) });
      return;
    }

    if (sourceType === "npm") {
      const name = pkg.trim();
      if (!name || !NPM_NAME.test(name)) {
        setFieldError("Enter a valid npm package name, e.g. mcp-server-fetch.");
        return;
      }
      setFieldError(null);
      onSubmit({ sourceType: "npm", source: name });
      return;
    }

    const files = rowsToFiles(pasteRows);
    if (Object.keys(files).length === 0) {
      setFieldError("Add at least one file, or load the example files.");
      return;
    }
    setFieldError(null);
    onSubmit({ sourceType: "paste", source: "pasted-files", files });
  };

  return (
    <form
      role="tabpanel"
      id={`scan-panel-${sourceType}`}
      aria-labelledby={`scan-tab-${sourceType}`}
      onSubmit={handleSubmit}
      noValidate
    >
      {sourceType === "github" && (
        <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
          <div>
            <label htmlFor="github-repo" className="mb-1.5 block text-sm font-medium text-foreground">
              Repository
            </label>
            <input
              id="github-repo"
              type="text"
              value={repoInput}
              disabled={busy}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => setRepoInput(e.target.value)}
              placeholder="owner/repo or https://github.com/owner/repo"
              aria-invalid={fieldError ? true : undefined}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label htmlFor="github-ref" className="mb-1.5 block text-sm font-medium text-foreground">
              Branch / tag <span className="font-normal text-muted">(optional)</span>
            </label>
            <input
              id="github-ref"
              type="text"
              value={refInput}
              disabled={busy}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => setRefInput(e.target.value)}
              placeholder="main"
              className={INPUT_CLASS}
            />
          </div>
        </div>
      )}

      {sourceType === "npm" && (
        <div>
          <label htmlFor="npm-package" className="mb-1.5 block text-sm font-medium text-foreground">
            Package name
          </label>
          <input
            id="npm-package"
            type="text"
            value={pkg}
            disabled={busy}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => setPkg(e.target.value)}
            placeholder="e.g. mcp-server-fetch"
            aria-invalid={fieldError ? true : undefined}
            className={INPUT_CLASS}
          />
          <p className="mt-1.5 text-xs text-muted">
            The published package is fetched and its MCP server entry points are scanned.
          </p>
        </div>
      )}

      {sourceType === "paste" && (
        <PasteEditor rows={pasteRows} onRowsChange={setPasteRows} disabled={busy} />
      )}

      <div className="mt-5 flex flex-col-reverse items-stretch gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="min-h-5 text-sm" role={fieldError ? "alert" : undefined}>
          {fieldError ? (
            <span className="text-critical">{fieldError}</span>
          ) : (
            <span className="text-muted">
              {sourceType === "paste"
                ? "Demo tip: the example files trigger multiple findings."
                : "Scans usually finish in a few seconds."}
            </span>
          )}
        </p>
        <button
          type="submit"
          disabled={busy}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-brand-contrast transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto"
        >
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Scanning…
            </>
          ) : (
            <>
              <ScanSearch className="h-4 w-4" aria-hidden="true" />
              Start security scan
            </>
          )}
        </button>
      </div>
    </form>
  );
}
