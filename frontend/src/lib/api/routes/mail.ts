import { apiFetch } from "../../http/client";
import type { ApiMailRecord, ApiMailRequest, ApiMailbox, MailType } from "../contracts/types";

export function listMailboxes(): Promise<ApiMailbox[]> {
  return apiFetch<ApiMailbox[]>("/mailboxes");
}

export function listMail(params: { date?: string; mailboxId?: string } = {}): Promise<ApiMailRecord[]> {
  const search = new URLSearchParams();
  if (params.date) search.set("date", params.date);
  if (params.mailboxId) search.set("mailboxId", params.mailboxId);
  const query = search.toString();
  return apiFetch<ApiMailRecord[]>(`/mail${query ? `?${query}` : ""}`);
}

export function createMail(payload: {
  mailboxId: string;
  date: string;
  type: MailType;
  receiverName?: string;
  senderInfo?: string;
  idempotencyKey: string;
}): Promise<ApiMailRecord> {
  const body: Record<string, unknown> = {
    mailboxId: payload.mailboxId,
    date: payload.date,
    type: payload.type,
  };
  if (payload.receiverName !== undefined && payload.receiverName !== "") {
    body.receiverName = payload.receiverName;
  }
  if (payload.senderInfo !== undefined && payload.senderInfo !== "") {
    body.senderInfo = payload.senderInfo;
  }
  return apiFetch<ApiMailRecord>("/mail", {
    method: "POST",
    headers: {
      "Idempotency-Key": payload.idempotencyKey,
    },
    body: JSON.stringify(body),
  });
}

export function updateMail(
  mailId: string,
  payload: Partial<{
    mailboxId: string;
    date: string;
    type: MailType;
    receiverName: string;
    senderInfo: string;
  }>
): Promise<ApiMailRecord> {
  return apiFetch<ApiMailRecord>(`/mail/${mailId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteMail(mailId: string): Promise<void> {
  return apiFetch<void>(`/mail/${mailId}`, {
    method: "DELETE",
  });
}

export function listMemberMailRequests(
  params: { status?: "ACTIVE" | "RESOLVED" | "ALL" } = {}
): Promise<ApiMailRequest[]> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  const query = search.toString();
  return apiFetch<ApiMailRequest[]>(`/mail-requests${query ? `?${query}` : ""}`);
}

export function createMailRequest(payload: {
  mailboxId: string;
  expectedSender?: string;
  description?: string;
  startDate?: string;
  endDate?: string;
}): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>("/mail-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelMailRequest(mailRequestId: string): Promise<void> {
  return apiFetch<void>(`/mail-requests/${mailRequestId}`, {
    method: "DELETE",
  });
}
