from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId

from repositories.mail_repository import find_mail_for_mailboxes
from repositories.mailboxes_repository import list_by_scope, member_mailbox_scope
from repositories.users_repository import find_user


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


class MailSummaryService:
    def __init__(
        self,
        *,
        users=None,
        mailboxes=None,
        mail=None,
    ) -> None:
        self._users = users
        self._mailboxes = mailboxes
        self._mail = mail

    def getWeeklySummary(self, userId: ObjectId, weekStart: date, weekEnd: date) -> dict[str, Any]:
        if self._users is None:
            user = find_user(userId)
        else:
            user = self._users.find_one({"_id": userId}, {"teamIds": 1})
        mailbox_query = member_mailbox_scope(
            {
                "_id": userId,
                "teamIds": user.get("teamIds") if user and isinstance(user.get("teamIds"), list) else [],
            }
        )

        if self._mailboxes is None:
            mailbox_docs = list_by_scope(mailbox_query)
        else:
            mailbox_docs = list(self._mailboxes.find(mailbox_query).sort([("displayName", 1), ("_id", 1)]))
        mailbox_ids = [m["_id"] for m in mailbox_docs]

        day_start = _day_bounds_utc(weekStart)
        day_end = _day_bounds_utc(weekEnd + timedelta(days=1))
        day_keys = _date_range(weekStart, weekEnd)

        totals: dict[ObjectId, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"letters": 0, "packages": 0}))
        if self._mail is None:
            cursor = find_mail_for_mailboxes(mailbox_ids=mailbox_ids, day_start=day_start, day_end=day_end)
        else:
            cursor = self._mail.find(
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

        mailboxes: list[dict[str, Any]] = []
        total_letters = 0
        total_packages = 0
        for mailbox in mailbox_docs:
            mailbox_totals = totals.get(mailbox["_id"], {})
            daily_breakdown = [
                {
                    "date": day_key,
                    "letters": mailbox_totals.get(day_key, {}).get("letters", 0),
                    "packages": mailbox_totals.get(day_key, {}).get("packages", 0),
                }
                for day_key in day_keys
            ]
            letters = sum(day["letters"] for day in daily_breakdown)
            packages = sum(day["packages"] for day in daily_breakdown)
            total_letters += letters
            total_packages += packages
            mailboxes.append(
                {
                    "mailboxId": str(mailbox["_id"]),
                    "mailboxName": mailbox.get("displayName", ""),
                    "mailboxType": _mailbox_kind(mailbox.get("type", "team")),
                    "letters": letters,
                    "packages": packages,
                    "dailyBreakdown": daily_breakdown,
                }
            )

        return {
            "weekStart": weekStart.isoformat(),
            "weekEnd": weekEnd.isoformat(),
            "totalLetters": total_letters,
            "totalPackages": total_packages,
            "mailboxes": mailboxes,
        }
