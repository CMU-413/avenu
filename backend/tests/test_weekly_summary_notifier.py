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


class FakeNotificationLogCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find_one(self, query, _projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return object()


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
    def test_notify_weekly_summary_logs_skipped_for_opted_out(self):
        user_id = ObjectId()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[CapturingChannel()],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": []}),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=1)),
            notificationLogs=logs,
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(result, {"status": "skipped", "reason": "opted_out", "channelResults": []})
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "skipped")
        self.assertEqual(logs.docs[0]["reason"], "opted_out")
        self.assertIsNone(logs.docs[0]["errorMessage"])

    def test_notify_weekly_summary_logs_failed_when_user_not_found(self):
        user_id = ObjectId()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[CapturingChannel()],
            users=FakeUsersCollection(None),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=1)),
            notificationLogs=logs,
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

        self.assertEqual(result, {"status": "failed", "reason": "user_not_found", "channelResults": []})
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "failed")
        self.assertEqual(logs.docs[0]["reason"], "user_not_found")
        self.assertIsNone(logs.docs[0]["errorMessage"])

    def test_notify_weekly_summary_logs_skipped_when_summary_is_empty(self):
        user_id = ObjectId()
        channel = CapturingChannel()
        summary_service = FakeSummaryService(self._summary(total_letters=0, total_packages=0))
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": ["email"]}),
            summaryService=summary_service,
            notificationLogs=logs,
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
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "skipped")
        self.assertEqual(logs.docs[0]["reason"], "empty_summary")

    def test_notify_weekly_summary_logs_sent_when_at_least_one_channel_succeeds(self):
        user_id = ObjectId()
        sent_channel = CapturingChannel()
        failed_channel = ReturningFailedChannel()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[failed_channel, sent_channel],
            users=FakeUsersCollection(
                {"_id": user_id, "email": "member@example.com", "fullname": "Member User", "notifPrefs": ["email"]}
            ),
            summaryService=FakeSummaryService(self._summary(total_letters=1, total_packages=2)),
            notificationLogs=logs,
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
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "sent")
        self.assertIsNone(logs.docs[0]["reason"])
        self.assertIsNotNone(logs.docs[0]["sentAt"])

    def test_notify_weekly_summary_logs_failed_when_all_channels_fail(self):
        user_id = ObjectId()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[RaisingChannel(), ReturningFailedChannel()],
            users=FakeUsersCollection({"_id": user_id, "notifPrefs": ["email"]}),
            summaryService=FakeSummaryService(self._summary(total_letters=3, total_packages=0)),
            notificationLogs=logs,
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
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "failed")
        self.assertEqual(logs.docs[0]["reason"], "all_channels_failed")
        self.assertIn("smtp offline", logs.docs[0]["errorMessage"])

    def test_notify_weekly_summary_duplicate_week_is_skipped_for_cron(self):
        user_id = ObjectId()
        channel = CapturingChannel()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "email": "member@example.com", "fullname": "Member User", "notifPrefs": ["email"]}),
            summaryService=FakeSummaryService(self._summary(total_letters=1, total_packages=0)),
            notificationLogs=logs,
        )

        first = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )
        second = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(first["status"], "sent")
        self.assertEqual(second, {"status": "skipped", "reason": "already_sent", "channelResults": []})
        self.assertEqual(channel.calls, 1)
        self.assertEqual(len(logs.docs), 2)
        self.assertEqual(logs.docs[0]["status"], "sent")
        self.assertEqual(logs.docs[1]["status"], "skipped")
        self.assertEqual(logs.docs[1]["reason"], "already_sent")

    def test_notify_weekly_summary_duplicate_week_is_skipped_for_admin(self):
        user_id = ObjectId()
        channel = CapturingChannel()
        logs = FakeNotificationLogCollection()
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "email": "member@example.com", "fullname": "Member User", "notifPrefs": ["email"]}),
            summaryService=FakeSummaryService(self._summary(total_letters=1, total_packages=1)),
            notificationLogs=logs,
        )

        first = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )
        second = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

        self.assertEqual(first["status"], "sent")
        self.assertEqual(second, {"status": "skipped", "reason": "already_sent", "channelResults": []})
        self.assertEqual(channel.calls, 1)
        self.assertEqual(len(logs.docs), 2)
        self.assertEqual(logs.docs[0]["triggeredBy"], "admin")
        self.assertEqual(logs.docs[1]["triggeredBy"], "admin")
        self.assertEqual(logs.docs[1]["reason"], "already_sent")

    def test_notify_weekly_summary_duplicate_check_uses_status_sent_only(self):
        user_id = ObjectId()
        channel = CapturingChannel()
        logs = FakeNotificationLogCollection(
            [
                {
                    "userId": user_id,
                    "type": "weekly-summary",
                    "weekStart": date(2026, 2, 15),
                    "status": "failed",
                    "reason": "all_channels_failed",
                    "triggeredBy": "cron",
                    "errorMessage": "smtp offline",
                    "sentAt": None,
                }
            ]
        )
        notifier = WeeklySummaryNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "email": "member@example.com", "fullname": "Member User", "notifPrefs": ["email"]}),
            summaryService=FakeSummaryService(self._summary(total_letters=2, total_packages=2)),
            notificationLogs=logs,
        )

        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="cron",
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(channel.calls, 1)
        self.assertEqual(len(logs.docs), 2)
        self.assertEqual(logs.docs[-1]["status"], "sent")

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
