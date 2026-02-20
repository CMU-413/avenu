import { apiFetch } from "../../http/client";
import type { ApiNotifyResult } from "../contracts/types";

export function sendWeeklySummaryNotification(payload: {
  userId: string;
  weekStart: string;
  weekEnd: string;
}): Promise<ApiNotifyResult> {
  return apiFetch<ApiNotifyResult>("/admin/notifications/summary", {
    method: "POST",
    body: JSON.stringify({
      userId: payload.userId,
      weekStart: payload.weekStart,
      weekEnd: payload.weekEnd,
    }),
  });
}
