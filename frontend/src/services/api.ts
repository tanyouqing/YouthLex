import {
  CreateSessionRequest,
  ErrorResponse,
  HealthResponse,
  SessionEnvelope,
  TurnRequest,
} from "../types/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE || "";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  code: string;
  traceId: string;
  details?: Record<string, unknown>;

  constructor(response: ErrorResponse) {
    super(response.error.message);
    this.name = "ApiError";
    this.code = response.error.code;
    this.traceId = response.trace_id;
    this.details = response.error.details;
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${API_PREFIX}${url}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err: unknown) {
    throw new Error(`网络请求失败: ${getErrorMessage(err)}`);
  }

  if (!res.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await res.json();
    } catch {
      throw new Error(`HTTP Error ${res.status}`);
    }
    throw new ApiError(errorData);
  }

  return res.json();
}

// ── 具体接口 ──────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  return apiCall<HealthResponse>("/health");
}

export async function createSession(req?: CreateSessionRequest): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>("/sessions", {
    method: "POST",
    body: JSON.stringify(req || {}),
  });
}

export async function sendTurn(sessionId: string, req: TurnRequest): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>(`/sessions/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getSession(sessionId: string): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>(`/sessions/${sessionId}`);
}
