import os
import unittest

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.special_case_notifier import SpecialCaseNotifier


class FakeUsersCollection:
    def __init__(self, user_doc):
        self._user_doc = user_doc

    def find_one(self, _query, _projection=None):
        return self._user_doc


class FakeNotificationLogCollection:
    def __init__(self):
        self.docs = []

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


class RaisingChannel:
    channel = "email"

    def send(self, _payload):
        raise RuntimeError("smtp offline")


class ReturningFailedChannel:
    channel = "email"

    def send(self, _payload):
        return {"channel": self.channel, "status": "failed", "error": "provider rejected"}


class SpecialCaseNotifierTests(unittest.TestCase):
    def test_notify_special_case_fails_and_logs_when_user_missing(self):
        logs = FakeNotificationLogCollection()
        notifier = SpecialCaseNotifier(
            channels=[CapturingChannel()],
            users=FakeUsersCollection(None),
            notificationLogs=logs,
        )

        result = notifier.notifySpecialCase(userId=ObjectId(), triggeredBy="admin")

        self.assertEqual(result, {"status": "failed", "reason": "user_not_found", "channelResults": []})
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["type"], "special-case")
        self.assertEqual(logs.docs[0]["templateType"], "mail-arrived")
        self.assertEqual(logs.docs[0]["status"], "failed")
        self.assertEqual(logs.docs[0]["reason"], "user_not_found")

    def test_notify_special_case_logs_sent_when_channel_succeeds(self):
        user_id = ObjectId()
        logs = FakeNotificationLogCollection()
        channel = CapturingChannel()
        notifier = SpecialCaseNotifier(
            channels=[channel],
            users=FakeUsersCollection({"_id": user_id, "email": "member@example.com", "fullname": "Member User"}),
            notificationLogs=logs,
        )

        result = notifier.notifySpecialCase(userId=user_id, triggeredBy="admin")

        self.assertEqual(result["status"], "sent")
        self.assertEqual(channel.last_payload["templateType"], "mail-arrived")
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "sent")
        self.assertIsNone(logs.docs[0]["mailboxId"])
        self.assertIsNone(logs.docs[0]["reason"])
        self.assertIsNotNone(logs.docs[0]["sentAt"])

    def test_notify_special_case_logs_failed_when_all_channels_fail(self):
        user_id = ObjectId()
        logs = FakeNotificationLogCollection()
        notifier = SpecialCaseNotifier(
            channels=[RaisingChannel(), ReturningFailedChannel()],
            users=FakeUsersCollection({"_id": user_id, "email": "member@example.com", "fullname": "Member User"}),
            notificationLogs=logs,
        )

        result = notifier.notifySpecialCase(userId=user_id, triggeredBy="admin")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "all_channels_failed")
        self.assertEqual(len(result["channelResults"]), 2)
        self.assertIn("smtp offline", result["channelResults"][0]["error"])
        self.assertEqual(len(logs.docs), 1)
        self.assertEqual(logs.docs[0]["status"], "failed")
        self.assertEqual(logs.docs[0]["reason"], "all_channels_failed")
        self.assertIn("smtp offline", logs.docs[0]["errorMessage"])


if __name__ == "__main__":
    unittest.main()
