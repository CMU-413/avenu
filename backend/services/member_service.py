from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId

from config import mail_collection, mailboxes_collection, users_collection


def _date_range(start_day: date, end_day: date) -> list[str]:
    days: list[str] = []
    current = start_day
    while current <= end_day:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _day_bounds_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _mailbox_kind(mailbox_type: str) -> str:
    return "personal" if mailbox_type == "user" else "company"


def list_member_mail_summary(*, user: dict[str, Any], start_day: date, end_day: date) -> dict[str, Any]:
    user_id = user["_id"]
    team_ids = user.get("teamIds") if isinstance(user.get("teamIds"), list) else []

    mailbox_or: list[dict[str, Any]] = [{"type": "user", "refId": user_id}]
    if team_ids:
        mailbox_or.append({"type": "team", "refId": {"$in": team_ids}})

    mailbox_docs = list(mailboxes_collection.find({"$or": mailbox_or}).sort([("type", 1), ("displayName", 1)]))
    mailbox_ids = [m["_id"] for m in mailbox_docs]

    day_start = _day_bounds_utc(start_day)
    day_end = _day_bounds_utc(end_day + timedelta(days=1))

    totals: dict[ObjectId, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"letters": 0, "packages": 0}))
    if mailbox_ids:
        cursor = mail_collection.find(
            {"mailboxId": {"$in": mailbox_ids}, "date": {"$gte": day_start, "$lt": day_end}},
            {"mailboxId": 1, "date": 1, "type": 1, "count": 1},
        )
        for row in cursor:
            mailbox_id = row["mailboxId"]
            row_date = row["date"]
            if row_date.tzinfo is None:
                row_date = row_date.replace(tzinfo=timezone.utc)
            day_key = row_date.astimezone(timezone.utc).date().isoformat()
            count = row.get("count", 0)
            if row.get("type") == "letter":
                totals[mailbox_id][day_key]["letters"] += count
            elif row.get("type") == "package":
                totals[mailbox_id][day_key]["packages"] += count

    day_keys = _date_range(start_day, end_day)
    mailboxes: list[dict[str, Any]] = []
    for mailbox in mailbox_docs:
        mailbox_totals = totals.get(mailbox["_id"], {})
        days = [
            {
                "date": day_key,
                "letters": mailbox_totals.get(day_key, {}).get("letters", 0),
                "packages": mailbox_totals.get(day_key, {}).get("packages", 0),
            }
            for day_key in day_keys
        ]
        mailboxes.append(
            {
                "mailboxId": str(mailbox["_id"]),
                "name": mailbox.get("displayName", ""),
                "type": _mailbox_kind(mailbox.get("type", "team")),
                "days": days,
            }
        )

    return {
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "mailboxes": mailboxes,
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
