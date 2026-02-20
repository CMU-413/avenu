import { apiFetch } from "../../http/client";
import type { ApiOptixTokenResult } from "../contracts/types";

export function bootstrapOptixSession(payload: {
  token: string;
  orgId: string | null;
  userId: string | null;
}): Promise<ApiOptixTokenResult> {
  return apiFetch<ApiOptixTokenResult>("/api/optix-token", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
