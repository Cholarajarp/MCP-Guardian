/** API client — owned by the scaffold (do NOT edit; report needed changes instead). */
import type { ScanRequest, ScanResult } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function startScan(req: ScanRequest): Promise<{ id: string }> {
  return request<{ id: string }>("/api/scans", { method: "POST", body: JSON.stringify(req) });
}

export function getScan(id: string): Promise<ScanResult> {
  return request<ScanResult>(`/api/scans/${encodeURIComponent(id)}`);
}

export function listScans(limit = 50): Promise<ScanResult[]> {
  return request<ScanResult[]>(`/api/scans?limit=${limit}`);
}
