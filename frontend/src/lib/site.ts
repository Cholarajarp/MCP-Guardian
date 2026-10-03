/** Project-level constants shared across components.
 *
 * The repository URL lives here rather than inline in the Navbar and Footer so
 * the two cannot drift apart, and so a fork only has one line to change.
 */
export const REPO_URL = "https://github.com/Cholarajarp/MCP-Guardian";

/** Attributes every outbound link should carry.
 *
 * `noopener` is the security-relevant half: without it the opened page gets a
 * live `window.opener` handle back to this one and can navigate it elsewhere
 * (reverse tabnabbing). `noreferrer` also suppresses the Referer header.
 */
export const EXTERNAL_LINK = {
  target: "_blank",
  rel: "noreferrer noopener",
} as const;
