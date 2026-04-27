from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from repositories.users_repository import update_notif_prefs
from services.mail_summary_service import MailSummaryService
from services.user_preferences import UNSET, normalize_effective_notification_state


def list_member_mail_summary(*, user: dict[str, Any], start_day: date, end_day: date) -> dict[str, Any]:
    summary = MailSummaryService().getWeeklySummary(userId=user["_id"], weekStart=start_day, weekEnd=end_day)

    return {
        "start": summary["weekStart"],
        "end": summary["weekEnd"],
        "mailboxes": [
            {
                "mailboxId": mailbox["mailboxId"],
                "name": mailbox["mailboxName"],
                "type": mailbox["mailboxType"],
                "days": mailbox["dailyBreakdown"],
            }
            for mailbox in summary["mailboxes"]
        ],
    }


def update_member_notification_preferences(
    *,
    user: dict[str, Any],
    email_notifications: bool | object = UNSET,
    sms_notifications: bool | object = UNSET,
) -> dict[str, Any]:
    normalized = normalize_effective_notification_state(
        current_user=user,
        email_notifications_patch=email_notifications,
        sms_notifications_patch=sms_notifications,
    )

    update_notif_prefs(user["_id"], normalized["notifPrefs"], updated_at=datetime.now(tz=timezone.utc))

    return {
        "id": str(user["_id"]),
        "emailNotifications": normalized["emailNotifications"],
        "smsNotifications": normalized["smsNotifications"],
        "hasPhone": normalized["hasPhone"],
        "hasSmsPhone": normalized["hasSmsPhone"],
    }
