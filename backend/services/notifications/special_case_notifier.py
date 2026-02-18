from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from config import notification_log_collection, users_collection
from services.notifications.interfaces import NotificationChannel
from services.notifications.log_repository import insert_special_case_notification_log
from services.notifications.types import (
    ChannelResult,
    NotificationLogStatus,
    NotifyReason,
    NotifyResult,
    NotifyTrigger,
    SpecialCaseNotificationPayload,
)


class SpecialCaseNotifier:
    def __init__(
        self,
        *,
        channels: list[NotificationChannel],
        users=users_collection,
        notificationLogs=notification_log_collection,
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
        insert_special_case_notification_log(
            self._notification_logs,
            user_id=user_id,
            status=status,
            reason=reason,
            triggered_by=triggered_by,
            error_message=error_message,
            sent_at=datetime.now(tz=timezone.utc) if status == "sent" else None,
        )

    def notifySpecialCase(
        self,
        *,
        userId: ObjectId,
        triggeredBy: NotifyTrigger,
    ) -> NotifyResult:
        user = self._users.find_one({"_id": userId}, {"email": 1, "fullname": 1})
        if user is None:
            self._log_attempt(
                user_id=userId,
                status="failed",
                reason="user_not_found",
                triggered_by=triggeredBy,
            )
            return {"status": "failed", "reason": "user_not_found", "channelResults": []}

        payload: SpecialCaseNotificationPayload = {
            "user": {
                "id": str(userId),
                "email": str(user.get("email", "")),
                "fullname": str(user.get("fullname", "")),
            },
            "triggeredBy": triggeredBy,
            "templateType": "mail-arrived",
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
            self._log_attempt(
                user_id=userId,
                status="sent",
                reason=None,
                triggered_by=triggeredBy,
            )
            return {"status": "sent", "channelResults": results}

        errors = [item["error"] for item in results if isinstance(item.get("error"), str) and item.get("error")]
        self._log_attempt(
            user_id=userId,
            status="failed",
            reason="all_channels_failed",
            triggered_by=triggeredBy,
            error_message="; ".join(errors) if errors else None,
        )
        return {"status": "failed", "reason": "all_channels_failed", "channelResults": results}
