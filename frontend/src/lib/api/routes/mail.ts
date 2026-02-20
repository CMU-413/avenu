import { apiFetch } from "../../http/client";
import type { ApiMailRecord, ApiMailRequest, ApiMailbox, MailType } from "../contracts/types";

export function listMailboxes(): Promise<ApiMailbox[]> {
  return apiFetch<ApiMailbox[]>("/api/mailboxes");
}

export function listMail(params: { date?: string; mailboxId?: string } = {}): Promise<ApiMailRecord[]> {
  const search = new URLSearchParams();
  if (params.date) search.set("date", params.date);
  if (params.mailboxId) search.set("mailboxId", params.mailboxId);
  const query = search.toString();
  return apiFetch<ApiMailRecord[]>(`/api/mail${query ? `?${query}` : ""}`);
}

export function createMail(payload: {
  mailboxId: string;
  date: string;
  type: MailType;
  count: number;
  idempotencyKey: string;
}): Promise<ApiMailRecord> {
  return apiFetch<ApiMailRecord>("/api/mail", {
    method: "POST",
    headers: {
      "Idempotency-Key": payload.idempotencyKey,
    },
    body: JSON.stringify({
      mailboxId: payload.mailboxId,
      date: payload.date,
      type: payload.type,
      count: payload.count,
    }),
  });
}

export function updateMail(
  mailId: string,
  payload: Partial<{
    mailboxId: string;
    date: string;
    type: MailType;
    count: number;
  }>
): Promise<ApiMailRecord> {
  return apiFetch<ApiMailRecord>(`/api/mail/${mailId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteMail(mailId: string): Promise<void> {
  return apiFetch<void>(`/api/mail/${mailId}`, {
    method: "DELETE",
  });
}

export function listMemberMailRequests(
  params: { status?: "ACTIVE" | "RESOLVED" | "ALL" } = {}
): Promise<ApiMailRequest[]> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  const query = search.toString();
  return apiFetch<ApiMailRequest[]>(`/api/mail-requests${query ? `?${query}` : ""}`);
}

export function createMailRequest(payload: {
  mailboxId: string;
  expectedSender?: string;
  description?: string;
  startDate?: string;
  endDate?: string;
}): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>("/api/mail-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelMailRequest(mailRequestId: string): Promise<void> {
  return apiFetch<void>(`/api/mail-requests/${mailRequestId}`, {
    method: "DELETE",
  });
}
