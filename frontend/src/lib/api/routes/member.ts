import { apiFetch } from "../../http/client";
import type { ApiMemberMailSummary, ApiMemberPreferences } from "../contracts/types";

export function getMemberMail(params: { start: string; end: string }): Promise<ApiMemberMailSummary> {
  const search = new URLSearchParams();
  search.set("start", params.start);
  search.set("end", params.end);
  return apiFetch<ApiMemberMailSummary>(`/member/mail?${search.toString()}`);
}

export function updateMemberPreferences(emailNotifications: boolean): Promise<ApiMemberPreferences> {
  return apiFetch<ApiMemberPreferences>("/member/preferences", {
    method: "PATCH",
    body: JSON.stringify({ emailNotifications }),
  });
}
