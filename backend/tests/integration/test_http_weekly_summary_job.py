from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

from .support import HttpIntegrationTestCase


class HttpWeeklySummaryJobIntegrationTests(HttpIntegrationTestCase):
    def test_internal_weekly_summary_requires_scheduler_token(self) -> None:
        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"):
            response = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers={"Idempotency-Key": "weekly-summary:2026-02-16"},
                json={"weekStart": "2026-02-16", "weekEnd": "2026-02-22"},
            )

        self.assertEqual(response.status_code, 401)

    def test_internal_weekly_summary_continues_when_one_recipient_transport_fails(self) -> None:
        from config import notification_log_collection

        week_start = date(2026, 2, 16)
        week_start_utc = datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc)

        fail_user = self.insert_user(
            email="weekly-fail@example.com",
            is_admin=False,
            fullname="Weekly Fail",
            notif_prefs=["email"],
        )
        ok_user = self.insert_user(
            email="weekly-ok@example.com",
            is_admin=False,
            fullname="Weekly Ok",
            notif_prefs=["email"],
        )
        fail_mailbox = self.insert_mailbox(
            owner_type="user",
            ref_id=fail_user["_id"],
            display_name="Fail Mailbox",
        )
        ok_mailbox = self.insert_mailbox(
            owner_type="user",
            ref_id=ok_user["_id"],
            display_name="Ok Mailbox",
        )
        self.insert_mail(
            mailbox_id=fail_mailbox,
            when=datetime(2026, 2, 18, 11, 0, tzinfo=timezone.utc),
            mail_type="letter",
            count=1,
        )
        self.insert_mail(
            mailbox_id=ok_mailbox,
            when=datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc),
            mail_type="letter",
            count=1,
        )

        def send_side_effect(_self, *, to: str, subject: str, html: str) -> str:
            if to == "weekly-fail@example.com":
                raise RuntimeError("smtp timeout")
            return "console-message-id"

        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"), patch(
            "services.notifications.providers.console_provider.ConsoleEmailProvider.send",
            autospec=True,
            side_effect=send_side_effect,
        ) as send_mock:
            response = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers={
                    "X-Scheduler-Token": "scheduler-secret",
                    "Idempotency-Key": "weekly-summary:2026-02-16",
                },
                json={"weekStart": "2026-02-16", "weekEnd": "2026-02-22"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["processed"], 2)
        self.assertEqual(body["sent"], 1)
        self.assertEqual(body["failed"], 1)
        self.assertEqual(body["errors"], 0)
        self.assertEqual(send_mock.call_count, 2)

        logs = list(
            notification_log_collection.find(
                {
                    "type": "weekly-summary",
                    "weekStart": week_start_utc,
                }
            )
        )
        self.assertEqual(len(logs), 2)
        statuses = {entry["status"] for entry in logs}
        self.assertEqual(statuses, {"sent", "failed"})
        failed_log = next(item for item in logs if item["status"] == "failed")
        self.assertEqual(failed_log["reason"], "all_channels_failed")
        self.assertIn("smtp timeout", failed_log.get("errorMessage", ""))

    def test_internal_weekly_summary_replays_on_reused_idempotency_key(self) -> None:
        from config import notification_log_collection

        user = self.insert_user(
            email="weekly-replay@example.com",
            is_admin=False,
            fullname="Weekly Replay",
            notif_prefs=["email"],
        )
        mailbox_id = self.insert_mailbox(
            owner_type="user",
            ref_id=user["_id"],
            display_name="Replay Mailbox",
        )
        self.insert_mail(
            mailbox_id=mailbox_id,
            when=datetime(2026, 2, 20, 10, 30, tzinfo=timezone.utc),
            mail_type="letter",
            count=1,
        )

        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"), patch(
            "services.notifications.providers.console_provider.ConsoleEmailProvider.send",
            autospec=True,
            return_value="console-message-id",
        ) as send_mock:
            headers = {
                "X-Scheduler-Token": "scheduler-secret",
                "Idempotency-Key": "weekly-summary:2026-02-16-replay",
            }
            first = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers=headers,
                json={"weekStart": "2026-02-16", "weekEnd": "2026-02-22"},
            )
            second = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers=headers,
                json={"weekStart": "2026-02-16", "weekEnd": "2026-02-22"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json(), second.get_json())
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(notification_log_collection.count_documents({"type": "weekly-summary"}), 1)
