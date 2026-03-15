import type {
  ModeSummary,
  RuntimeSnapshot,
  SessionBootstrapPayload,
  SessionBootstrapResponse,
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export function getRuntime(): Promise<RuntimeSnapshot> {
  return request<RuntimeSnapshot>("/api/runtime");
}

export function getModes(): Promise<ModeSummary[]> {
  return request<ModeSummary[]>("/api/live/modes");
}

export function startSession(
  payload: SessionBootstrapPayload,
): Promise<SessionBootstrapResponse> {
  return request<SessionBootstrapResponse>("/api/live/session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resolveLiveWebSocketUrl(websocketPath: string): string {
  if (websocketPath.startsWith("ws://") || websocketPath.startsWith("wss://")) {
    return websocketPath;
  }

  const normalizedPath = websocketPath.startsWith("/") ? websocketPath : `/${websocketPath}`;

  if (API_BASE_URL) {
    const baseUrl = new URL(API_BASE_URL);
    const protocol = baseUrl.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${baseUrl.host}${normalizedPath}`;
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${normalizedPath}`;
  }

  return `ws://localhost:8000${normalizedPath}`;
}
