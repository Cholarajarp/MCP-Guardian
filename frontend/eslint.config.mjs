import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextCoreWebVitals,
  {
    ignores: [".next/**", "node_modules/**", "out/**"],
    // This React Compiler advisory is introduced by the Next.js 16 security
    // upgrade. The existing asynchronous workspace/control effects preserve
    // behavior intentionally and are covered by generation guards.
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default config;
