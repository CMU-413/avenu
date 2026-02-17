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
