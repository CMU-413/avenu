from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId

from repositories.notification_logs_repository import (
    find_sent_weekly_summary as repo_find_sent_weekly_summary,
    insert_special_case_log,
    insert_weekly_summary_log,
)
from services.notifications.types import NotificationLogEntry, NotificationLogStatus, NotifyReason, NotifyTrigger


WEEKLY_SUMMARY_TYPE = "weekly-summary"
SPECIAL_CASE_TYPE = "special-case"
MAIL_ARRIVED_TEMPLATE_TYPE = "mail-arrived"


def _to_utc_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def find_sent_weekly_summary(
    collection,
    *,
    user_id: ObjectId,
    week_start: date,
) -> NotificationLogEntry | None:
    if collection is None:
        return repo_find_sent_weekly_summary(user_id=user_id, week_start=week_start)
    return collection.find_one(
        {"userId": user_id, "type": WEEKLY_SUMMARY_TYPE, "weekStart": _to_utc_datetime(week_start), "status": "sent"}
    )


def insert_notification_log(
    collection,
    *,
    user_id: ObjectId,
    week_start: date,
    status: NotificationLogStatus,
    reason: NotifyReason | None,
    triggered_by: NotifyTrigger,
    error_message: str | None,
    sent_at: datetime | None,
) -> None:
    if collection is None:
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
    collection.insert_one(
        {
            "userId": user_id,
            "type": WEEKLY_SUMMARY_TYPE,
            "weekStart": _to_utc_datetime(week_start),
            "templateType": None,
            "mailboxId": None,
            "status": status,
            "reason": reason,
            "triggeredBy": triggered_by,
            "errorMessage": error_message,
            "sentAt": sent_at,
            "createdAt": datetime.now(tz=timezone.utc),
        }
    )


def insert_special_case_notification_log(
    collection,
    *,
    user_id: ObjectId,
    status: NotificationLogStatus,
    reason: NotifyReason | None,
    triggered_by: NotifyTrigger,
    error_message: str | None,
    sent_at: datetime | None,
) -> None:
    if collection is None:
        insert_special_case_log(
            user_id=user_id,
            status=status,
            reason=reason,
            triggered_by=triggered_by,
            error_message=error_message,
            sent_at=sent_at,
        )
        return
    collection.insert_one(
        {
            "userId": user_id,
            "type": SPECIAL_CASE_TYPE,
            "weekStart": None,
            "templateType": MAIL_ARRIVED_TEMPLATE_TYPE,
            "mailboxId": None,
            "status": status,
            "reason": reason,
            "triggeredBy": triggered_by,
            "errorMessage": error_message,
            "sentAt": sent_at,
            "createdAt": datetime.now(tz=timezone.utc),
        }
    )
