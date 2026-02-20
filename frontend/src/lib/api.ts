export type MailboxType = "user" | "team";
export type MailType = "letter" | "package";

export interface ApiMailbox {
  id: string;
  type: MailboxType;
  refId: string;
  displayName: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApiMailRecord {
  id: string;
  mailboxId: string;
  date: string;
  type: MailType;
  count: number;
  createdAt: string;
  updatedAt: string;
}

export interface ApiUser {
  id: string;
  optixId: number;
  isAdmin: boolean;
  fullname: string;
  email: string;
  phone: string | null;
  teamIds: string[];
  notifPrefs: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ApiTeam {
  id: string;
  optixId: number;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApiSessionMe {
  id: string;
  email: string;
  fullname: string;
  isAdmin: boolean;
  teamIds: string[];
  emailNotifications: boolean;
}

export interface ApiMemberMailboxDay {
  date: string;
  letters: number;
  packages: number;
}

export interface ApiMemberMailboxSummary {
  mailboxId: string;
  name: string;
  type: "personal" | "company";
  days: ApiMemberMailboxDay[];
}

export interface ApiMemberMailSummary {
  start: string;
  end: string;
  mailboxes: ApiMemberMailboxSummary[];
}

export interface ApiMemberPreferences {
  id: string;
  emailNotifications: boolean;
}

export type ApiMailRequestStatus = "ACTIVE" | "CANCELLED" | "RESOLVED";
export type ApiMailRequestNotificationStatus = "SENT" | "FAILED";

export interface ApiMailRequest {
  id: string;
  memberId: string;
  mailboxId: string;
  expectedSender: string | null;
  description: string | null;
  startDate: string | null;
  endDate: string | null;
  status: ApiMailRequestStatus;
  resolvedAt: string | null;
  resolvedBy: string | null;
  lastNotificationStatus: ApiMailRequestNotificationStatus | null;
  lastNotificationAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiNotifyChannelResult {
  channel: string;
  status: "sent" | "failed";
  messageId?: string;
  error?: string;
}

export interface ApiNotifyResult {
  status: "sent" | "skipped" | "failed";
  reason?: string;
  channelResults: ApiNotifyChannelResult[];
}

export interface ApiOptixTokenResult {
  created: boolean;
  user: ApiUser;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

export function listUsers(): Promise<ApiUser[]> {
  return apiFetch<ApiUser[]>("/api/users");
}

export function listTeams(): Promise<ApiTeam[]> {
  return apiFetch<ApiTeam[]>("/api/teams");
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

export function getMemberMail(params: { start: string; end: string }): Promise<ApiMemberMailSummary> {
  const search = new URLSearchParams();
  search.set("start", params.start);
  search.set("end", params.end);
  return apiFetch<ApiMemberMailSummary>(`/api/member/mail?${search.toString()}`);
}

export function updateMemberPreferences(emailNotifications: boolean): Promise<ApiMemberPreferences> {
  return apiFetch<ApiMemberPreferences>("/api/member/preferences", {
    method: "PATCH",
    body: JSON.stringify({ emailNotifications }),
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

export function listAdminMailRequests(filters: { mailboxId?: string; memberId?: string } = {}): Promise<ApiMailRequest[]> {
  const search = new URLSearchParams();
  if (filters.mailboxId) search.set("mailboxId", filters.mailboxId);
  if (filters.memberId) search.set("memberId", filters.memberId);
  const query = search.toString();
  return apiFetch<ApiMailRequest[]>(`/api/admin/mail-requests${query ? `?${query}` : ""}`);
}

export function resolveAdminMailRequest(id: string): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>(`/api/admin/mail-requests/${id}/resolve`, {
    method: "POST",
  });
}

export function retryAdminMailRequestNotification(id: string): Promise<ApiMailRequest> {
  return apiFetch<ApiMailRequest>(`/api/admin/mail-requests/${id}/retry-notification`, {
    method: "POST",
  });
}

export function sendWeeklySummaryNotification(payload: {
  userId: string;
  weekStart: string;
  weekEnd: string;
}): Promise<ApiNotifyResult> {
  return apiFetch<ApiNotifyResult>("/api/admin/notifications/summary", {
    method: "POST",
    body: JSON.stringify({
      userId: payload.userId,
      weekStart: payload.weekStart,
      weekEnd: payload.weekEnd,
    }),
  });
}

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
