from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId
from pymongo.collection import Collection

from services.notifications.types import NotificationLogEntry, NotificationLogStatus, NotifyReason, NotifyTrigger


WEEKLY_SUMMARY_TYPE = "weekly-summary"

def _to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def find_sent_weekly_summary(
    collection: Collection,
    *,
    user_id: ObjectId,
    week_start: date,
) -> NotificationLogEntry | None:
    return collection.find_one(
        {
            "userId": user_id,
            "type": WEEKLY_SUMMARY_TYPE,
            "weekStart": _to_utc_datetime(week_start),
            "status": "sent",
        }
    )


def insert_notification_log(
    collection: Collection,
    *,
    user_id: ObjectId,
    week_start: date,
    status: NotificationLogStatus,
    reason: NotifyReason | None,
    triggered_by: NotifyTrigger,
    error_message: str | None,
    sent_at: datetime | None,
) -> None:
    collection.insert_one(
        {
            "userId": user_id,
            "type": WEEKLY_SUMMARY_TYPE,
            "weekStart": _to_utc_datetime(week_start),
            "status": status,
            "reason": reason,
            "triggeredBy": triggered_by,
            "errorMessage": error_message,
            "sentAt": sent_at,
            "createdAt": datetime.now(tz=timezone.utc),
        }
    )
