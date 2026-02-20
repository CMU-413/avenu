import { apiFetch } from "../../http/client";
import type { ApiSessionMe } from "../contracts/types";

export function sessionLogin(email: string): Promise<void> {
  return apiFetch<void>("/api/session/login", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function sessionLogout(): Promise<void> {
  return apiFetch<void>("/api/session/logout", {
    method: "POST",
  });
}

export function sessionMe(): Promise<ApiSessionMe> {
  return apiFetch<ApiSessionMe>("/api/session/me");
}
