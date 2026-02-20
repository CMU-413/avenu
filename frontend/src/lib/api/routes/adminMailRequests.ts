import { apiFetch } from "../../http/client";
import type { ApiMailRequest } from "../contracts/types";

export function listAdminMailRequests(filters: { mailboxId?: string; memberId?: string } = {}): Promise<ApiMailRequest[]> {
  const search = new URLSearchParams();
  if (filters.mailboxId) search.set("mailboxId", filters.mailboxId);
  if (filters.memberId) search.set("memberId", filters.memberId);
  const query = search.toString();
  return apiFetch<ApiMailRequest[]>(`/admin/mail-requests${query ? `?${query}` : ""}`);
}

export function resolveAdminMailRequest(id: string): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>(`/admin/mail-requests/${id}/resolve`, {
    method: "POST",
  });
}

export function retryAdminMailRequestNotification(id: string): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>(`/admin/mail-requests/${id}/retry-notification`, {
    method: "POST",
  });
}
