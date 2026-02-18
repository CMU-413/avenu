from __future__ import annotations

from datetime import date
from typing import Any

from bson import ObjectId

from config import users_collection
from services.mail_summary_service import MailSummaryService
from services.notifications.interfaces import NotificationChannel
from services.notifications.types import ChannelResult, NotifyResult, NotifyTrigger, WeeklySummaryNotificationPayload


def _email_opted_in(user: dict[str, Any]) -> bool:
    prefs = user.get("notifPrefs")
    if not isinstance(prefs, list):
        return False
    return "email" in prefs


class WeeklySummaryNotifier:
    def __init__(
        self,
        *,
        channels: list[NotificationChannel],
        summaryService: MailSummaryService | None = None,
        users=users_collection,
    ) -> None:
        self._channels = list(channels)
        self._summary_service = summaryService or MailSummaryService()
        self._users = users

    def notifyWeeklySummary(
        self,
        *,
        userId: ObjectId,
        weekStart: date,
        weekEnd: date,
        triggeredBy: NotifyTrigger,
    ) -> NotifyResult:
        user = self._users.find_one({"_id": userId}, {"email": 1, "fullname": 1, "notifPrefs": 1})
        if user is None:
            return {"status": "failed", "reason": "user_not_found", "channelResults": []}

        if not _email_opted_in(user):
            return {"status": "skipped", "reason": "opted_out", "channelResults": []}

        summary = self._summary_service.getWeeklySummary(userId=userId, weekStart=weekStart, weekEnd=weekEnd)
        if summary["totalLetters"] + summary["totalPackages"] == 0:
            return {"status": "skipped", "reason": "empty_summary", "channelResults": []}

        payload: WeeklySummaryNotificationPayload = {
            "user": {
                "id": str(userId),
                "email": str(user.get("email", "")),
                "fullname": str(user.get("fullname", "")),
            },
            "triggeredBy": triggeredBy,
            "summary": summary,
        }

        results: list[ChannelResult] = []
        for channel in self._channels:
            try:
                channel_result = channel.send(payload)
            except Exception as exc:
                results.append({"channel": getattr(channel, "channel", "unknown"), "status": "failed", "error": str(exc)})
                continue

            normalized: ChannelResult = {
                "channel": str(channel_result.get("channel", getattr(channel, "channel", "unknown"))),
                "status": "sent" if channel_result.get("status") == "sent" else "failed",
            }
            if isinstance(channel_result.get("messageId"), str) and channel_result.get("messageId"):
                normalized["messageId"] = channel_result["messageId"]
            if isinstance(channel_result.get("error"), str) and channel_result.get("error"):
                normalized["error"] = channel_result["error"]
            results.append(normalized)

        if any(item["status"] == "sent" for item in results):
            return {"status": "sent", "channelResults": results}
        return {"status": "failed", "reason": "all_channels_failed", "channelResults": results}
