import type { Config } from "tailwindcss";

/**
 * Design tokens live in src/app/globals.css as CSS variables (light + dark).
 * Every color below consumes a token — never raw white/black — so both themes
 * stay finished with zero component-level dark: overrides.
 *
 * Severity colors are exposed two ways on purpose:
 *   - `severity.critical` … `severity.info`  → text-severity-critical, etc.
 *   - top-level `critical` … `info` aliases  → text-critical, bg-high, etc.
 * Both point at the same --severity-* tokens.
 */
const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        /* Backdrop for `gap-px` grids — the reference's divider device. */
        hairline: "var(--hairline)",
        "hairline-strong": "var(--hairline-strong)",
        foreground: "var(--foreground)",
        secondary: "var(--secondary)",
        muted: "var(--muted)",
        faint: "var(--faint)",
        /* Steel/secondary metal (reference #c0c0c0). */
        chrome: "var(--chrome)",
        /* Ink for text over photography or a dark wash — fixed in both themes
           because the wash beneath it is dark either way. */
        "on-media": "var(--on-media)",
        "on-media-dim": "var(--on-media-dim)",
        brand: {
          DEFAULT: "var(--brand)",
          hover: "var(--brand-hover)",
          subtle: "var(--brand-subtle)",
          contrast: "var(--brand-contrast)",
          /* Accessible text/link variant — use for ANY orange text. */
          text: "var(--brand-text)",
        },
        positive: {
          DEFAULT: "var(--positive)",
          subtle: "var(--positive-subtle)",
          border: "var(--positive-border)",
          ink: "var(--positive-ink)",
        },
        caution: {
          DEFAULT: "var(--caution)",
          subtle: "var(--caution-subtle)",
          border: "var(--caution-border)",
        },
        code: {
          string: "var(--code-string)",
          keyword: "var(--code-keyword)",
        },
        severity: {
          critical: "var(--severity-critical)",
          high: "var(--severity-high)",
          medium: "var(--severity-medium)",
          low: "var(--severity-low)",
          info: "var(--severity-info)",
        },
        /* Top-level aliases. `ink` is the text color that passes on each solid
           severity fill — a token, not a dark: override, because every fill
           lightens in dark mode so the ink has to flip with it. */
        critical: {
          DEFAULT: "var(--severity-critical)",
          ink: "var(--severity-critical-ink)",
        },
        high: {
          DEFAULT: "var(--severity-high)",
          ink: "var(--severity-high-ink)",
        },
        medium: {
          DEFAULT: "var(--severity-medium)",
          ink: "var(--severity-medium-ink)",
        },
        low: {
          DEFAULT: "var(--severity-low)",
          ink: "var(--severity-low-ink)",
        },
        info: {
          DEFAULT: "var(--severity-info)",
          ink: "var(--severity-info-ink)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        /* One face, as the reference does. `display` stays as a named alias so
           the ~12 files using font-display keep working, but it resolves to
           Inter: the weight (900) and tracking carry the display voice, not a
           second family. */
        display: ["var(--font-inter)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: [
          "var(--font-mono)",
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
      },
      /* SQUARE CORNERS.
         The reference has no radius on buttons, cards, inputs or panels — only
         on status dots and pills. Zeroing the scale here squares the entire app
         from one place instead of editing ~96 `rounded-*` usages across 23
         files, and it keeps future code square by default. `full` is preserved
         because the reference genuinely uses it for dots and avatars. */
      borderRadius: {
        none: "0",
        sm: "0",
        DEFAULT: "0",
        md: "0",
        lg: "0",
        xl: "0",
        "2xl": "0",
        "3xl": "0",
        full: "9999px",
      },
    },
  },
  plugins: [],
};

export default config;
