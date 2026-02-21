from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from repositories.notification_logs_repository import insert_special_case_log
from repositories.users_repository import find_basic_profile
from services.notifications.interfaces import NotificationChannel
from services.notifications.log_repository import insert_special_case_notification_log
from services.notifications.types import (
    ChannelResult,
    NotificationLogStatus,
    NotifyReason,
    NotifyResult,
    NotifyTrigger,
    SpecialCaseMailRequestContext,
    SpecialCaseNotificationPayload,
)

CHANNEL_PREFS: dict[str, str] = {
    "email": "email",
    "sms": "text",
}


def _notif_prefs(user: dict) -> set[str]:
    prefs = user.get("notifPrefs")
    if not isinstance(prefs, list):
        return set()
    return {item for item in prefs if isinstance(item, str)}


def _preferred_channels(channels: list[NotificationChannel], user: dict) -> list[NotificationChannel]:
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


class SpecialCaseNotifier:
    def __init__(
        self,
        *,
        channels: list[NotificationChannel],
        users=None,
        notificationLogs=None,
    ) -> None:
        self._channels = list(channels)
        self._users = users
        self._notification_logs = notificationLogs

    def _log_attempt(
        self,
        *,
        user_id: ObjectId,
        status: NotificationLogStatus,
        reason: NotifyReason | None,
        triggered_by: NotifyTrigger,
        error_message: str | None = None,
    ) -> None:
        sent_at = datetime.now(tz=timezone.utc) if status == "sent" else None
        if self._notification_logs is None:
            insert_special_case_log(
                user_id=user_id,
                status=status,
                reason=reason,
                triggered_by=triggered_by,
                error_message=error_message,
                sent_at=sent_at,
            )
            return
        insert_special_case_notification_log(
            self._notification_logs,
            user_id=user_id,
            status=status,
            reason=reason,
            triggered_by=triggered_by,
            error_message=error_message,
            sent_at=sent_at,
        )

    def notifySpecialCase(
        self,
        *,
        userId: ObjectId,
        triggeredBy: NotifyTrigger,
        mailRequest: SpecialCaseMailRequestContext | None = None,
    ) -> NotifyResult:
        if self._users is None:
            user = find_basic_profile(userId)
        else:
            user = self._users.find_one({"_id": userId}, {"email": 1, "fullname": 1, "phone": 1, "notifPrefs": 1})
        if user is None:
            self._log_attempt(
                user_id=userId,
                status="failed",
                reason="user_not_found",
                triggered_by=triggeredBy,
            )
            return {"status": "failed", "reason": "user_not_found", "channelResults": []}

        preferred_channels = _preferred_channels(self._channels, user)
        if not preferred_channels:
            self._log_attempt(
                user_id=userId,
                status="skipped",
                reason="opted_out",
                triggered_by=triggeredBy,
            )
            return {"status": "skipped", "reason": "opted_out", "channelResults": []}

        payload: SpecialCaseNotificationPayload = {
            "user": {
                "id": str(userId),
                "email": str(user.get("email", "")),
                "fullname": str(user.get("fullname", "")),
                "phone": str(user.get("phone", "")),
            },
            "triggeredBy": triggeredBy,
            "templateType": "mail-arrived",
            "mailRequest": mailRequest,
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
                status="sent",
                reason=None,
                triggered_by=triggeredBy,
            )
            return {"status": "sent", "channelResults": results}

        if any(item["status"] == "failed" for item in results):
            errors = [item["error"] for item in results if isinstance(item.get("error"), str) and item.get("error")]
            self._log_attempt(
                user_id=userId,
                status="failed",
                reason="all_channels_failed",
                triggered_by=triggeredBy,
                error_message="; ".join(errors) if errors else None,
            )
            return {"status": "failed", "reason": "all_channels_failed", "channelResults": results}

        self._log_attempt(
            user_id=userId,
            status="skipped",
            reason=None,
            triggered_by=triggeredBy,
        )
        return {"status": "skipped", "channelResults": results}
