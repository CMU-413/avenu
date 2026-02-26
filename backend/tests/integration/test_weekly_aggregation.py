from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from bson import ObjectId

from support import MongoIntegrationTestCase


class WeeklyAggregationIntegrationTests(MongoIntegrationTestCase):
    def test_weekly_summary_uses_deterministic_utc_window_boundaries(self) -> None:
        from repositories.mail_repository import insert_mail
        from repositories.mailboxes_repository import insert_mailbox
        from repositories.users_repository import insert_user
        from services.mail_summary_service import MailSummaryService

        now = datetime.now(tz=timezone.utc)
        user_id = ObjectId()
        week_start = date(2026, 2, 16)
        week_end = date(2026, 2, 22)

        insert_user(
            {
                "_id": user_id,
                "optixId": 3001,
                "isAdmin": False,
                "fullname": "Week User",
                "email": "week-user@example.com",
                "phone": None,
                "teamIds": [],
                "notifPrefs": ["email"],
                "createdAt": now,
                "updatedAt": now,
            }
        )
        mailbox_id = insert_mailbox(
            {
                "type": "user",
                "refId": user_id,
                "displayName": "Week Mailbox",
                "createdAt": now,
                "updatedAt": now,
            }
        )

        in_window_start = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)
        in_window_end = datetime(2026, 2, 22, 23, 59, tzinfo=timezone.utc)
        out_of_window = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        insert_mail(
            {
                "mailboxId": mailbox_id,
                "date": in_window_start,
                "type": "letter",
                "count": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        insert_mail(
            {
                "mailboxId": mailbox_id,
                "date": in_window_end,
                "type": "letter",
                "count": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        insert_mail(
            {
                "mailboxId": mailbox_id,
                "date": out_of_window,
                "type": "package",
                "count": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        )

        summary = MailSummaryService().getWeeklySummary(userId=user_id, weekStart=week_start, weekEnd=week_end)

        self.assertEqual(summary["weekStart"], "2026-02-16")
        self.assertEqual(summary["weekEnd"], "2026-02-22")
        self.assertEqual(summary["totalLetters"], 2)
        self.assertEqual(summary["totalPackages"], 0)
        self.assertEqual(len(summary["mailboxes"]), 1)
        self.assertEqual(summary["mailboxes"][0]["letters"], 2)
        self.assertEqual(summary["mailboxes"][0]["packages"], 0)
        self.assertEqual(summary["mailboxes"][0]["dailyBreakdown"][0]["date"], "2026-02-16")
        self.assertEqual(summary["mailboxes"][0]["dailyBreakdown"][-1]["date"], "2026-02-22")
