import { ApiError } from "./errors";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const initHeaders = init?.headers || {};
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...initHeaders,
    },
  });

  if (!response.ok) {
    const fallback = `Request failed (${response.status})`;
    let message = fallback;
    try {
      const body = await response.json();
      if (body?.error && typeof body.error === "string") {
        message = body.error;
      }
    } catch {
      // Ignore JSON parse failures for non-JSON error bodies.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
