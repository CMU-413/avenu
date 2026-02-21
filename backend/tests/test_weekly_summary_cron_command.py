import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app
from scripts.run_weekly_summary_cron import build_default_notifier, run_weekly_summary_cron_command
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier


class FakeUsersCollection:
    def __init__(self, user_doc):
        self._user_doc = user_doc

    def find_one(self, _query, _projection=None):
        return self._user_doc


class FakeSummaryService:
    def __init__(self, summary):
        self._summary = summary

    def getWeeklySummary(self, **_kwargs):
        return self._summary


class FakeNotificationLogCollection:
    def __init__(self):
        self.docs = []

    def find_one(self, _query, _projection=None):
        return None

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return object()


class WeeklySummaryCronCommandTests(unittest.TestCase):
    def test_build_default_notifier_uses_shared_channel_builder(self):
        sentinel_channel = object()
        with patch(
            "scripts.run_weekly_summary_cron.build_notification_channels",
            return_value=[sentinel_channel],
        ) as channels_builder_mock:
            notifier = build_default_notifier(testing=False)

        channels_builder_mock.assert_called_once_with(testing=False)
        self.assertEqual(notifier._channels, [sentinel_channel])

    def test_manual_command_uses_same_notifier_entrypoint(self):
        captured = {}
        sentinel_notifier = object()
        fixed_now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)

        def fake_job_runner(*, notifier, now, logger):
            captured["notifier"] = notifier
            captured["now"] = now
            captured["logger"] = logger
            return {
                "weekStart": date(2026, 2, 9),
                "weekEnd": date(2026, 2, 15),
                "processed": 0,
                "sent": 0,
                "skipped": 0,
                "failed": 0,
                "errors": 0,
            }

        result = run_weekly_summary_cron_command(
            notifier=sentinel_notifier,
            now=fixed_now,
            logger=None,
            job_runner=fake_job_runner,
            app_factory=lambda **_kwargs: create_app(testing=True, ensure_db_indexes_on_startup=False),
        )

        self.assertIs(captured["notifier"], sentinel_notifier)
        self.assertEqual(captured["now"], fixed_now)
        self.assertEqual(result["weekStart"], date(2026, 2, 9))

    def test_manual_command_console_provider_path_emits_expected_output(self):
        user_id = ObjectId()
        notifier = WeeklySummaryNotifier(
            channels=[EmailChannel(ConsoleEmailProvider())],
            users=FakeUsersCollection(
                {
                    "_id": user_id,
                    "email": "member@example.com",
                    "fullname": "Member User",
                    "notifPrefs": ["email"],
                }
            ),
            summaryService=FakeSummaryService(
                {
                    "weekStart": "2026-02-09",
                    "weekEnd": "2026-02-15",
                    "totalLetters": 2,
                    "totalPackages": 1,
                    "mailboxes": [],
                }
            ),
            notificationLogs=FakeNotificationLogCollection(),
        )

        def fake_job_runner(*, notifier, now, logger):
            notifier.notifyWeeklySummary(
                userId=user_id,
                weekStart=date(2026, 2, 9),
                weekEnd=date(2026, 2, 15),
                triggeredBy="cron",
            )
            return {
                "weekStart": date(2026, 2, 9),
                "weekEnd": date(2026, 2, 15),
                "processed": 1,
                "sent": 1,
                "skipped": 0,
                "failed": 0,
                "errors": 0,
            }

        with io.StringIO() as buf, redirect_stdout(buf):
            result = run_weekly_summary_cron_command(
                notifier=notifier,
                now=datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc),
                logger=None,
                job_runner=fake_job_runner,
                app_factory=lambda **_kwargs: create_app(testing=True, ensure_db_indexes_on_startup=False),
            )
            output = buf.getvalue()

        self.assertEqual(result["sent"], 1)
        self.assertIn("=== EMAIL SEND ===", output)
        self.assertIn("To: member@example.com", output)
        self.assertIn("Subject: Your Avenu Mail Summary (Feb 09", output)


if __name__ == "__main__":
    unittest.main()
