from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from config import users_collection
from services.mail_summary_service import MailSummaryService


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


def update_member_email_notifications(*, user: dict[str, Any], enabled: bool) -> dict[str, Any]:
    notif_prefs = user.get("notifPrefs") if isinstance(user.get("notifPrefs"), list) else []
    next_prefs = [pref for pref in notif_prefs if pref != "email"]
    if enabled:
        next_prefs.append("email")

    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"notifPrefs": next_prefs, "updatedAt": datetime.now(tz=timezone.utc)}},
    )

    return {
        "id": str(user["_id"]),
        "emailNotifications": enabled,
    }
