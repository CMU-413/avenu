import os
import unittest
from datetime import date, datetime, time, timedelta, timezone

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.mail_summary_service import MailSummaryService


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, spec):
        docs = list(self._docs)
        for key, direction in reversed(spec):
            reverse = direction < 0
            docs.sort(key=lambda row: row.get(key), reverse=reverse)
        return FakeCursor(docs)

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find_one(self, query, _projection=None):
        for doc in self._docs:
            if _matches(doc, query):
                return doc
        return None

    def find(self, query, _projection=None):
        return FakeCursor([doc for doc in self._docs if _matches(doc, query)])


def _matches(doc, query):
    for key, value in query.items():
        if key == "$or":
            if not any(_matches(doc, subquery) for subquery in value):
                return False
            continue
        if isinstance(value, dict):
            if "$in" in value and doc.get(key) not in value["$in"]:
                return False
            if "$gte" in value and doc.get(key) < value["$gte"]:
                return False
            if "$lt" in value and doc.get(key) >= value["$lt"]:
                return False
            continue
        if doc.get(key) != value:
            return False
    return True


def _at(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=timezone.utc)


class MailSummaryServiceTests(unittest.TestCase):
    def test_get_weekly_summary_single_mailbox(self):
        user_id = ObjectId()
        mailbox_id = ObjectId()
        week_start = date(2026, 2, 15)
        week_end = date(2026, 2, 21)

        service = MailSummaryService(
            users=FakeCollection([{"_id": user_id, "teamIds": []}]),
            mailboxes=FakeCollection([{"_id": mailbox_id, "type": "user", "refId": user_id, "displayName": "Jane Doe"}]),
            mail=FakeCollection(
                [
                    {"mailboxId": mailbox_id, "date": _at(week_start), "type": "letter", "count": 2},
                    {"mailboxId": mailbox_id, "date": _at(week_start + timedelta(days=1), 9), "type": "package", "count": 1},
                    {"mailboxId": mailbox_id, "date": _at(week_start + timedelta(days=1), 15), "type": "letter", "count": 3},
                ]
            ),
        )

        summary = service.getWeeklySummary(userId=user_id, weekStart=week_start, weekEnd=week_end)

        self.assertEqual(summary["weekStart"], "2026-02-15")
        self.assertEqual(summary["weekEnd"], "2026-02-21")
        self.assertEqual(summary["totalLetters"], 5)
        self.assertEqual(summary["totalPackages"], 1)
        self.assertEqual(len(summary["mailboxes"]), 1)
        mailbox = summary["mailboxes"][0]
        self.assertEqual(mailbox["mailboxName"], "Jane Doe")
        self.assertEqual(mailbox["mailboxType"], "personal")
        self.assertEqual(mailbox["letters"], 5)
        self.assertEqual(mailbox["packages"], 1)
        self.assertEqual(mailbox["dailyBreakdown"][0], {"date": "2026-02-15", "letters": 2, "packages": 0})
        self.assertEqual(mailbox["dailyBreakdown"][1], {"date": "2026-02-16", "letters": 3, "packages": 1})
        self.assertEqual(mailbox["dailyBreakdown"][-1]["date"], "2026-02-21")

    def test_get_weekly_summary_multiple_mailboxes_are_sorted(self):
        user_id = ObjectId()
        team_id = ObjectId()
        personal_mailbox = ObjectId()
        team_mailbox = ObjectId()
        week_start = date(2026, 2, 15)
        week_end = date(2026, 2, 21)

        service = MailSummaryService(
            users=FakeCollection([{"_id": user_id, "teamIds": [team_id]}]),
            mailboxes=FakeCollection(
                [
                    {"_id": personal_mailbox, "type": "user", "refId": user_id, "displayName": "Zulu User"},
                    {"_id": team_mailbox, "type": "team", "refId": team_id, "displayName": "Acme Co"},
                ]
            ),
            mail=FakeCollection(
                [
                    {"mailboxId": personal_mailbox, "date": _at(week_start), "type": "letter", "count": 1},
                    {"mailboxId": team_mailbox, "date": _at(week_start), "type": "package", "count": 2},
                ]
            ),
        )

        summary = service.getWeeklySummary(userId=user_id, weekStart=week_start, weekEnd=week_end)

        self.assertEqual(summary["totalLetters"], 1)
        self.assertEqual(summary["totalPackages"], 2)
        self.assertEqual([mb["mailboxName"] for mb in summary["mailboxes"]], ["Acme Co", "Zulu User"])
        self.assertEqual(summary["mailboxes"][0]["mailboxType"], "company")
        self.assertEqual(summary["mailboxes"][1]["mailboxType"], "personal")
        self.assertEqual(summary["mailboxes"][0]["dailyBreakdown"][0]["date"], "2026-02-15")
        self.assertEqual(summary["mailboxes"][0]["dailyBreakdown"][-1]["date"], "2026-02-21")

    def test_get_weekly_summary_empty_week_returns_structured_zero_summary(self):
        user_id = ObjectId()
        mailbox_id = ObjectId()
        week_start = date(2026, 2, 15)
        week_end = date(2026, 2, 21)

        service = MailSummaryService(
            users=FakeCollection([{"_id": user_id, "teamIds": []}]),
            mailboxes=FakeCollection([{"_id": mailbox_id, "type": "user", "refId": user_id, "displayName": "No Mail"}]),
            mail=FakeCollection([]),
        )

        summary = service.getWeeklySummary(userId=user_id, weekStart=week_start, weekEnd=week_end)

        self.assertEqual(summary["totalLetters"], 0)
        self.assertEqual(summary["totalPackages"], 0)
        self.assertEqual(len(summary["mailboxes"]), 1)
        self.assertEqual(summary["mailboxes"][0]["letters"], 0)
        self.assertEqual(summary["mailboxes"][0]["packages"], 0)
        self.assertEqual(len(summary["mailboxes"][0]["dailyBreakdown"]), 7)
        self.assertTrue(all(day["letters"] == 0 and day["packages"] == 0 for day in summary["mailboxes"][0]["dailyBreakdown"]))

    def test_get_weekly_summary_includes_start_and_excludes_end_plus_one_day(self):
        user_id = ObjectId()
        mailbox_id = ObjectId()
        week_start = date(2026, 2, 15)
        week_end = date(2026, 2, 21)
        start_dt = _at(week_start, 0, 0)
        end_last_dt = _at(week_end, 23, 59)
        end_plus_one_dt = _at(week_end + timedelta(days=1), 0, 0)
        before_start_dt = _at(week_start - timedelta(days=1), 23, 59)

        service = MailSummaryService(
            users=FakeCollection([{"_id": user_id, "teamIds": []}]),
            mailboxes=FakeCollection([{"_id": mailbox_id, "type": "user", "refId": user_id, "displayName": "Boundary"}]),
            mail=FakeCollection(
                [
                    {"mailboxId": mailbox_id, "date": start_dt, "type": "letter", "count": 1},
                    {"mailboxId": mailbox_id, "date": end_last_dt, "type": "package", "count": 2},
                    {"mailboxId": mailbox_id, "date": end_plus_one_dt, "type": "letter", "count": 10},
                    {"mailboxId": mailbox_id, "date": before_start_dt, "type": "package", "count": 10},
                ]
            ),
        )

        summary = service.getWeeklySummary(userId=user_id, weekStart=week_start, weekEnd=week_end)

        self.assertEqual(summary["totalLetters"], 1)
        self.assertEqual(summary["totalPackages"], 2)
        daily = summary["mailboxes"][0]["dailyBreakdown"]
        self.assertEqual(daily[0], {"date": "2026-02-15", "letters": 1, "packages": 0})
        self.assertEqual(daily[-1], {"date": "2026-02-21", "letters": 0, "packages": 2})


if __name__ == "__main__":
    unittest.main()
