export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

import { TriageRequest, TriageResponse } from "../types/triage";

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function runTriageSync(request: TriageRequest): Promise<TriageResponse> {
  const response = await fetch(`${API_BASE}/api/v1/triage/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export async function getSessionSnapshot(sessionId: string): Promise<TriageResponse> {
  const response = await fetch(`${API_BASE}/api/v1/triage/session/${sessionId}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}
