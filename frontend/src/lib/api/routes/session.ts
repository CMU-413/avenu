import { apiFetch } from "../../http/client";
import type { ApiSessionMe } from "../contracts/types";

export function requestMagicLink(email: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/session/login", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function redeemMagicLink(params: { tokenId: string; signature: string }): Promise<void> {
  return apiFetch<void>("/session/redeem", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function sessionLogout(): Promise<void> {
  return apiFetch<void>("/session/logout", {
    method: "POST",
  });
}

export function sessionMe(): Promise<ApiSessionMe> {
  return apiFetch<ApiSessionMe>("/session/me");
}
