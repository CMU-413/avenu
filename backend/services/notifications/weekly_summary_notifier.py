from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from bson import ObjectId

from repositories.notification_logs_repository import find_sent_weekly_summary, insert_weekly_summary_log
from repositories.users_repository import find_for_notification
from services.mail_summary_service import MailSummaryService
from services.notifications.interfaces import NotificationChannel
from services.notifications.log_repository import (
    find_sent_weekly_summary as find_sent_weekly_summary_legacy,
    insert_notification_log as insert_notification_log_legacy,
)
from services.notifications.types import (
    ChannelResult,
    NotificationLogStatus,
    NotifyReason,
    NotifyResult,
    NotifyTrigger,
    WeeklySummaryNotificationPayload,
)


CHANNEL_PREFS: dict[str, str] = {
    "email": "email",
    "sms": "text",
}


def _notif_prefs(user: dict[str, Any]) -> set[str]:
    prefs = user.get("notifPrefs")
    if not isinstance(prefs, list):
        return set()
    return {item for item in prefs if isinstance(item, str)}


def _preferred_channels(channels: list[NotificationChannel], user: dict[str, Any]) -> list[NotificationChannel]:
    prefs = _notif_prefs(user)
    if not prefs:
        return []
    filtered: list[NotificationChannel] = []
    for channel in channels:
        channel_name = str(getattr(channel, "channel", "")).strip().lower()
        mapped_pref = CHANNEL_PREFS.get(channel_name)
        if mapped_pref is None or mapped_pref in prefs:
            filtered.append(channel)
    return filtered


def _normalize_channel_result(channel: NotificationChannel, result: ChannelResult) -> ChannelResult:
    status_value = result.get("status")
    if status_value == "sent":
        normalized_status = "sent"
    elif status_value == "skipped":
        normalized_status = "skipped"
    else:
        normalized_status = "failed"
    normalized: ChannelResult = {
        "channel": str(result.get("channel", getattr(channel, "channel", "unknown"))),
        "status": normalized_status,
    }
    if isinstance(result.get("messageId"), str) and result.get("messageId"):
        normalized["messageId"] = result["messageId"]
    if isinstance(result.get("error"), str) and result.get("error"):
        normalized["error"] = result["error"]
    return normalized


def _normalize_week_start(value: date) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    return date(value.year, value.month, value.day)


def _error_message_from_channel_results(results: list[ChannelResult]) -> str | None:
    errors: list[str] = []
    for result in results:
        error_value = result.get("error")
        if isinstance(error_value, str) and error_value:
            errors.append(error_value)
    if not errors:
        return None
    return "; ".join(errors)


class WeeklySummaryNotifier:
    def __init__(
        self,
        *,
        channels: list[NotificationChannel],
        summaryService: MailSummaryService | None = None,
        users=None,
        notificationLogs=None,
    ) -> None:
        self._channels = list(channels)
        self._summary_service = summaryService or MailSummaryService()
        self._users = users
        self._notification_logs = notificationLogs

    def _log_attempt(
        self,
        *,
        user_id: ObjectId,
        week_start: date,
        status: NotificationLogStatus,
        reason: NotifyReason | None,
        triggered_by: NotifyTrigger,
        error_message: str | None = None,
    ) -> None:
        sent_at = datetime.now(tz=timezone.utc) if status == "sent" else None
        if self._notification_logs is None:
            insert_weekly_summary_log(
                user_id=user_id,
                week_start=week_start,
                status=status,
                reason=reason,
                triggered_by=triggered_by,
                error_message=error_message,
                sent_at=sent_at,
            )
            return
        insert_notification_log_legacy(
            self._notification_logs,
            user_id=user_id,
            week_start=week_start,
            status=status,
            reason=reason,
            triggered_by=triggered_by,
            error_message=error_message,
            sent_at=sent_at,
        )

    def notifyWeeklySummary(
        self,
        *,
        userId: ObjectId,
        weekStart: date,
        weekEnd: date,
        triggeredBy: NotifyTrigger,
    ) -> NotifyResult:
        normalized_week_start = _normalize_week_start(weekStart)
        if self._notification_logs is None:
            existing_sent = find_sent_weekly_summary(
                user_id=userId,
                week_start=normalized_week_start,
            )
        else:
            existing_sent = find_sent_weekly_summary_legacy(
                self._notification_logs,
                user_id=userId,
                week_start=normalized_week_start,
            )
        if existing_sent is not None:
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="skipped",
                reason="already_sent",
                triggered_by=triggeredBy,
            )
            return {"status": "skipped", "reason": "already_sent", "channelResults": []}

        if self._users is None:
            user = find_for_notification(userId)
        else:
            user = self._users.find_one({"_id": userId}, {"email": 1, "fullname": 1, "phone": 1, "notifPrefs": 1})
        if user is None:
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="failed",
                reason="user_not_found",
                triggered_by=triggeredBy,
            )
            return {"status": "failed", "reason": "user_not_found", "channelResults": []}

        preferred_channels = _preferred_channels(self._channels, user)
        if not preferred_channels:
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="skipped",
                reason="opted_out",
                triggered_by=triggeredBy,
            )
            return {"status": "skipped", "reason": "opted_out", "channelResults": []}

        summary = self._summary_service.getWeeklySummary(userId=userId, weekStart=weekStart, weekEnd=weekEnd)
        if summary["totalLetters"] + summary["totalPackages"] == 0:
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="skipped",
                reason="empty_summary",
                triggered_by=triggeredBy,
            )
            return {"status": "skipped", "reason": "empty_summary", "channelResults": []}

        payload: WeeklySummaryNotificationPayload = {
            "user": {
                "id": str(userId),
                "email": str(user.get("email", "")),
                "fullname": str(user.get("fullname", "")),
                "phone": str(user.get("phone", "")),
            },
            "triggeredBy": triggeredBy,
            "summary": summary,
        }

        results: list[ChannelResult] = []
        for channel in preferred_channels:
            try:
                channel_result = channel.send(payload)
            except Exception as exc:
                results.append({"channel": getattr(channel, "channel", "unknown"), "status": "failed", "error": str(exc)})
                continue
            results.append(_normalize_channel_result(channel, channel_result))

        if any(item["status"] == "sent" for item in results):
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="sent",
                reason=None,
                triggered_by=triggeredBy,
            )
            return {"status": "sent", "channelResults": results}
        if any(item["status"] == "failed" for item in results):
            self._log_attempt(
                user_id=userId,
                week_start=normalized_week_start,
                status="failed",
                reason="all_channels_failed",
                triggered_by=triggeredBy,
                error_message=_error_message_from_channel_results(results),
            )
            return {"status": "failed", "reason": "all_channels_failed", "channelResults": results}

        self._log_attempt(
            user_id=userId,
            week_start=normalized_week_start,
            status="skipped",
            reason=None,
            triggered_by=triggeredBy,
        )
        return {"status": "skipped", "channelResults": results}
