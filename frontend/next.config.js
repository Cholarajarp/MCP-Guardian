/** MCP Guardian — Next config. CSP + security headers; API origin from NEXT_PUBLIC_API_URL. */
const isProduction = process.env.NODE_ENV === "production";
const apiOrigin = safeOrigin(process.env.NEXT_PUBLIC_API_URL);

const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'" + (isProduction ? "" : " 'unsafe-eval'"),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin} ${apiOrigin.replace(/^http/, "ws")}`,
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
].join("; ");

module.exports = {
  poweredByHeader: false,
  // Authoritative API origin for browser code (see src/lib/api.ts).
  env: {
    NEXT_PUBLIC_API_URL: apiOrigin,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
};

function safeOrigin(value) {
  try {
    const origin = new URL(value);
    return origin.origin === "null" ? "http://localhost:8000" : origin.origin;
  } catch {
    return "http://localhost:8000";
  }
}
