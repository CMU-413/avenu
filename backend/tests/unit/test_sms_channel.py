import os
import unittest
from datetime import date

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.channels.sms_channel import SMSChannel
from services.notifications.providers.sms_provider import SMSProvider, SMSProviderError


class FakeSMSProvider(SMSProvider):
    def __init__(self):
        self.calls = []

    def send(self, *, to: str, body: str):
        self.calls.append({"to": to, "body": body})
        return {"messageId": "SMFAKE123"}


class RaisingSMSProvider(SMSProvider):
    def send(self, *, to: str, body: str):
        _ = to, body
        raise SMSProviderError("provider down")


class SMSChannelTests(unittest.TestCase):
    def test_send_weekly_summary_returns_skipped_when_phone_missing(self):
        provider = FakeSMSProvider()
        channel = SMSChannel(provider)

        result = channel.send(
            {
                "user": {
                    "id": str(ObjectId()),
                    "email": "member@example.com",
                    "fullname": "Member User",
                },
                "triggeredBy": "cron",
                "summary": {
                    "weekStart": "2026-02-15",
                    "weekEnd": "2026-02-21",
                    "totalLetters": 1,
                    "totalPackages": 2,
                    "mailboxes": [],
                },
            }
        )

        self.assertEqual(result["channel"], "sms")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("missing phone", result["error"])
        self.assertEqual(provider.calls, [])

    def test_send_special_case_formats_body_and_calls_provider(self):
        provider = FakeSMSProvider()
        channel = SMSChannel(provider)

        result = channel.send(
            {
                "user": {
                    "id": str(ObjectId()),
                    "email": "member@example.com",
                    "fullname": "Member User",
                    "phone": "+15550001111",
                },
                "triggeredBy": "admin",
                "templateType": "mail-arrived",
                "mailRequest": {
                    "requestId": str(ObjectId()),
                    "mailboxId": str(ObjectId()),
                    "expectedSender": "Acme Sender",
                },
            }
        )

        self.assertEqual(result, {"channel": "sms", "status": "sent", "messageId": "SMFAKE123"})
        self.assertEqual(provider.calls[0]["to"], "+15550001111")
        self.assertIn("Acme Sender", provider.calls[0]["body"])

    def test_send_returns_failed_when_provider_raises(self):
        channel = SMSChannel(RaisingSMSProvider())

        result = channel.send(
            {
                "user": {
                    "id": str(ObjectId()),
                    "email": "member@example.com",
                    "fullname": "Member User",
                    "phone": "+15550001111",
                },
                "triggeredBy": "admin",
                "templateType": "mail-arrived",
                "mailRequest": None,
            }
        )

        self.assertEqual(result["channel"], "sms")
        self.assertEqual(result["status"], "failed")
        self.assertIn("provider down", result["error"])

    def test_send_returns_sent_with_message_id_on_success(self):
        provider = FakeSMSProvider()
        channel = SMSChannel(provider)

        result = channel.send(
            {
                "user": {
                    "id": str(ObjectId()),
                    "email": "member@example.com",
                    "fullname": "Member User",
                    "phone": "+15550001111",
                },
                "triggeredBy": "cron",
                "summary": {
                    "weekStart": date(2026, 2, 15),
                    "weekEnd": date(2026, 2, 21),
                    "totalLetters": 3,
                    "totalPackages": 1,
                    "mailboxes": [],
                },
            }
        )

        self.assertEqual(result, {"channel": "sms", "status": "sent", "messageId": "SMFAKE123"})
        self.assertEqual(len(provider.calls), 1)
        self.assertIn("Letters: 3", provider.calls[0]["body"])


if __name__ == "__main__":
    unittest.main()
