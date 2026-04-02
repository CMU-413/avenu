from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .support import HttpIntegrationTestCase


class HttpMailDashboardConsistencyIntegrationTests(HttpIntegrationTestCase):
    def test_admin_mail_logging_matches_member_dashboard_and_weekly_summary_totals(self) -> None:
        from config import mail_collection
        from services.mail_summary_service import MailSummaryService

        week_start = date(2026, 2, 16)
        week_end = date(2026, 2, 22)
        range_start = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)
        range_end = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        admin = self.insert_user(
            email="admin-dashboard@example.com",
            is_admin=True,
            fullname="Admin Dashboard",
        )
        member = self.insert_user(
            email="member-dashboard@example.com",
            is_admin=False,
            fullname="Member Dashboard",
        )
        mailbox_id = self.insert_mailbox(
            owner_type="user",
            ref_id=member["_id"],
            display_name="Member Dashboard Mailbox",
        )

        self.login(email=admin["email"])
        create_headers_1 = {"Idempotency-Key": "mail-create-1"}
        create_headers_2 = {"Idempotency-Key": "mail-create-2"}

        created_letter = self.client.post(
            "/api/mail",
            headers=create_headers_1,
            json={
                "mailboxId": str(mailbox_id),
                "date": "2026-02-17T10:00:00+00:00",
                "type": "letter",
                "count": 2,
            },
        )
        created_package = self.client.post(
            "/api/mail",
            headers=create_headers_2,
            json={
                "mailboxId": str(mailbox_id),
                "date": "2026-02-19T13:30:00+00:00",
                "type": "package",
                "count": 1,
            },
        )

        self.assertEqual(created_letter.status_code, 201)
        self.assertEqual(created_package.status_code, 201)
        self.assertEqual(self.client.post("/api/session/logout").status_code, 204)

        self.login(email=member["email"])
        dashboard_response = self.client.get("/api/member/mail?start=2026-02-16&end=2026-02-22")
        self.assertEqual(dashboard_response.status_code, 200)

        dashboard_payload = dashboard_response.get_json()
        self.assertIsInstance(dashboard_payload, dict)
        mailboxes = dashboard_payload["mailboxes"]

        dashboard_letters = 0
        dashboard_packages = 0
        for mailbox in mailboxes:
            for day in mailbox["days"]:
                dashboard_letters += int(day["letters"])
                dashboard_packages += int(day["packages"])

        weekly_summary = MailSummaryService().getWeeklySummary(
            userId=member["_id"],
            weekStart=week_start,
            weekEnd=week_end,
        )

        persisted_rows = list(
            mail_collection.find(
                {
                    "mailboxId": mailbox_id,
                    "date": {"$gte": range_start, "$lt": range_end},
                }
            )
        )
        persisted_letters = sum(
            int(row.get("count", 0))
            for row in persisted_rows
            if row.get("type") == "letter"
        )
        persisted_packages = sum(
            int(row.get("count", 0))
            for row in persisted_rows
            if row.get("type") == "package"
        )

        self.assertEqual(dashboard_letters, 2)
        self.assertEqual(dashboard_packages, 1)
        self.assertEqual(dashboard_letters, weekly_summary["totalLetters"])
        self.assertEqual(dashboard_packages, weekly_summary["totalPackages"])
        self.assertEqual(dashboard_letters, persisted_letters)
        self.assertEqual(dashboard_packages, persisted_packages)
