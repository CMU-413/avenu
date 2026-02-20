from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from bson import ObjectId

from config import notification_log_collection


def _week_start_as_utc_datetime(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def find_sent_weekly_summary(*, user_id: ObjectId, week_start: date) -> dict[str, Any] | None:
    return notification_log_collection.find_one(
        {
            "userId": user_id,
            "type": "weekly-summary",
            "weekStart": _week_start_as_utc_datetime(week_start),
            "status": "sent",
        },
        {"_id": 1},
    )


def insert_weekly_summary_log(
    *,
    user_id: ObjectId,
    week_start: date,
    status: str,
    reason: str | None,
    triggered_by: str,
    error_message: str | None,
    sent_at: datetime | None,
) -> None:
    notification_log_collection.insert_one(
        {
            "userId": user_id,
            "type": "weekly-summary",
            "weekStart": _week_start_as_utc_datetime(week_start),
            "status": status,
            "reason": reason,
            "triggeredBy": triggered_by,
            "errorMessage": error_message,
            "sentAt": sent_at,
            "createdAt": datetime.now(tz=timezone.utc),
        }
    )


def insert_special_case_log(
    *,
    user_id: ObjectId,
    status: str,
    reason: str | None,
    triggered_by: str,
    error_message: str | None,
    sent_at: datetime | None,
) -> None:
    notification_log_collection.insert_one(
        {
            "userId": user_id,
            "type": "special-case",
            "templateType": "mail-arrived",
            "mailboxId": None,
            "weekStart": None,
            "status": status,
            "reason": reason,
            "triggeredBy": triggered_by,
            "errorMessage": error_message,
            "sentAt": sent_at,
            "createdAt": datetime.now(tz=timezone.utc),
        }
    )
