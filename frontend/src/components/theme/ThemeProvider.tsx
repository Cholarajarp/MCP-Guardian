"use client";

import { MotionConfig } from "framer-motion";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/** Class-based theme boundary shared by Tailwind (`darkMode: ["class"]`) and components. */
export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider {...props}>
      {/* framer-motion animates inline styles from JS, so the
          prefers-reduced-motion block in globals.css cannot reach it.
          reducedMotion="user" is the one place that does: it drops
          transform/layout animation when the OS asks, keeping opacity. */}
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </NextThemesProvider>
  );
}
