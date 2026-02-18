import os
import unittest
from datetime import date

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier


class FakeUsersCollection:
    def __init__(self, user_doc):
        self._user_doc = user_doc
        self.find_one_calls = 0

    def find_one(self, _query, _projection=None):
        self.find_one_calls += 1
        return self._user_doc


class FakeSummaryService:
    def __init__(self, summary):
        self._summary = summary
        self.calls = 0

    def getWeeklySummary(self, **_kwargs):
        self.calls += 1
        return self._summary


class CapturingChannel:
    channel = "email"

    def __init__(self):
        self.calls = 0
        self.last_payload = None

    def send(self, payload):
        self.calls += 1
        self.last_payload = payload
        return {"channel": self.channel, "status": "sent"}


class ReturningFailedChannel:
    channel = "email"

    def send(self, _payload):
        return {"channel": self.channel, "status": "failed", "error": "provider rejected"}


class RaisingChannel:
    channel = "email"

    def send(self, _payload):
        raise RuntimeError("smtp offline")


class WeeklySummaryNotifierTests(unittest.TestCase):
    def test_notify_weekly_summary_skips_when_user_opted_out(self):
        user_id = ObjectId()
        notifier = WeeklySummaryNotifier(
            channels=[CapturingChannel()],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": []}),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=1)),
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(result, {"status": "skipped", "reason": "opted_out", "channelResults": []})

    def test_notify_weekly_summary_fails_when_user_not_found(self):
        user_id = ObjectId()
        notifier = WeeklySummaryNotifier(
            channels=[CapturingChannel()],
            users=FakeUsersCollection(None),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=1)),
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

        self.assertEqual(result, {"status": "failed", "reason": "user_not_found", "channelResults": []})

    def test_notify_weekly_summary_skips_when_summary_is_empty(self):
        user_id = ObjectId()
        channel = CapturingChannel()
        summary_service = FakeSummaryService(self._summary(total_letters=0, total_packages=0))
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": ["email"]}),
            summaryService=summary_service,
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(result, {"status": "skipped", "reason": "empty_summary", "channelResults": []})
        self.assertEqual(summary_service.calls, 1)
        self.assertEqual(channel.calls, 0)

    def test_notify_weekly_summary_sends_when_at_least_one_channel_succeeds(self):
        user_id = ObjectId()
        sent_channel = CapturingChannel()
        failed_channel = ReturningFailedChannel()
        notifier = WeeklySummaryNotifier(
            channels=[failed_channel, sent_channel],
            users=FakeUsersCollection(
                {"_id": user_id, "email": "member@example.com", "fullname": "Member User", "notifPrefs": ["email"]}
            ),
            summaryService=FakeSummaryService(self._summary(total_letters=1, total_packages=2)),
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(result["channelResults"]), 2)
        self.assertEqual(result["channelResults"][0]["status"], "failed")
        self.assertEqual(result["channelResults"][1]["status"], "sent")
        self.assertEqual(sent_channel.last_payload["user"]["id"], str(user_id))
        self.assertEqual(sent_channel.last_payload["user"]["email"], "member@example.com")
        self.assertEqual(sent_channel.last_payload["triggeredBy"], "admin")

    def test_notify_weekly_summary_collects_channel_failure_without_throwing(self):
        user_id = ObjectId()
        notifier = WeeklySummaryNotifier(
            channels=[RaisingChannel(), ReturningFailedChannel()],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": ["email"]}),
            summaryService=FakeSummaryService(self._summary(total_letters=3, total_packages=0)),
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "all_channels_failed")
        self.assertEqual(len(result["channelResults"]), 2)
        self.assertEqual(result["channelResults"][0]["status"], "failed")
        self.assertIn("smtp offline", result["channelResults"][0]["error"])

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
