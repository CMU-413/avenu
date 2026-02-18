import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from app import create_app
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import EmailProvider
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier


class FakeEmailProvider(EmailProvider):
    def __init__(self):
        self.calls = []

    def send(self, *, to: str, subject: str, html: str) -> str:
        self.calls.append({"to": to, "subject": subject, "html": html})
        return "fake-message-id"


class RaisingEmailProvider(EmailProvider):
    def send(self, *, to: str, subject: str, html: str) -> str:
        raise RuntimeError("provider down")


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


class EmailChannelTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(testing=True, ensure_db_indexes_on_startup=False)

    def test_send_renders_template_and_uses_provider(self):
        provider = FakeEmailProvider()
        channel = EmailChannel(provider)

        with self.app.app_context():
            result = channel.send(self._payload())

        self.assertEqual(result, {"channel": "email", "status": "sent", "messageId": "fake-message-id"})
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["to"], "member@example.com")
        self.assertEqual(provider.calls[0]["subject"], "Your Avenu Mail Summary (Feb 15–Feb 21)")
        self.assertIn("Weekly Mail Summary", provider.calls[0]["html"])

    def test_send_returns_failed_when_provider_raises(self):
        channel = EmailChannel(RaisingEmailProvider())

        with self.app.app_context():
            result = channel.send(self._payload())

        self.assertEqual(result["channel"], "email")
        self.assertEqual(result["status"], "failed")
        self.assertIn("provider down", result["error"])

    def test_send_builds_subject_from_date_objects(self):
        provider = FakeEmailProvider()
        channel = EmailChannel(provider)
        payload = self._payload()
        payload["summary"]["weekStart"] = date(2026, 2, 15)
        payload["summary"]["weekEnd"] = date(2026, 2, 21)

        with self.app.app_context():
            channel.send(payload)

        self.assertEqual(provider.calls[0]["subject"], "Your Avenu Mail Summary (Feb 15–Feb 21)")

    def test_console_provider_prints_and_returns_message_id(self):
        provider = ConsoleEmailProvider()

        with io.StringIO() as buf, redirect_stdout(buf):
            message_id = provider.send(to="member@example.com", subject="Subject", html="<p>Hello</p>")
            output = buf.getvalue()

        self.assertEqual(message_id, "console-message-id")
        self.assertIn("=== EMAIL SEND ===", output)
        self.assertIn("To: member@example.com", output)
        self.assertIn("Subject: Subject", output)

    def test_weekly_summary_notifier_dispatches_to_email_channel(self):
        user_id = ObjectId()
        provider = FakeEmailProvider()
        channel = EmailChannel(provider)
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection(
                {
                    "_id": user_id,
                    "email": "member@example.com",
                    "fullname": "Member User",
                    "notifPrefs": ["email"],
                }
            ),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=1)),
        )

        with self.app.app_context():
            result = notifier.notifyWeeklySummary(
                userId=user_id,
                weekStart=date(2026, 2, 15),
                weekEnd=date(2026, 2, 21),
                triggeredBy="cron",
            )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["channelResults"], [{"channel": "email", "status": "sent", "messageId": "fake-message-id"}])
        self.assertEqual(len(provider.calls), 1)

    def _payload(self):
        return {
            "user": {
                "id": str(ObjectId()),
                "email": "member@example.com",
                "fullname": "Member User",
            },
            "triggeredBy": "cron",
            "summary": self._summary(total_letters=1, total_packages=2),
        }

    def _summary(self, *, total_letters: int, total_packages: int):
        return {
            "weekStart": "2026-02-15",
            "weekEnd": "2026-02-21",
            "totalLetters": total_letters,
            "totalPackages": total_packages,
            "mailboxes": [],
        }


if __name__ == "__main__":
    unittest.main()
