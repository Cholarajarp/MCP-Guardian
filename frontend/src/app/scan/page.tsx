import type { Metadata } from "next";
import { ScanView } from "../../components/scan/ScanView";

export const metadata: Metadata = {
  title: "Scan an MCP server | MCP Guardian",
  description:
    "Scan a GitHub repo, npm package, or pasted MCP server code for security findings, a risk score, and a generated Cedar policy.",
};

export default function ScanPage() {
  return <ScanView />;
}
