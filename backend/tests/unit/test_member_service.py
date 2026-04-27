import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.member_service import update_member_notification_preferences


class MemberServiceTests(unittest.TestCase):
    def test_update_member_preferences_partial_patch_leaves_omitted_fields_unchanged(self):
        user_id = ObjectId()
        user = {"_id": user_id, "notifPrefs": ["email"], "phone": "+15550001111"}

        with patch("services.member_service.update_notif_prefs") as update_mock:
            response = update_member_notification_preferences(
                user=user,
                sms_notifications=True,
            )

        update_mock.assert_called_once()
        self.assertEqual(update_mock.call_args.args[0], user_id)
        self.assertEqual(update_mock.call_args.args[1], ["email", "text"])
        self.assertEqual(
            response,
            {
                "id": str(user_id),
                "emailNotifications": True,
                "smsNotifications": True,
                "hasPhone": True,
                "hasSmsPhone": True,
            },
        )

    def test_update_member_preferences_rejects_sms_without_phone(self):
        user = {"_id": ObjectId(), "notifPrefs": ["email"], "phone": "   "}

        with patch("services.member_service.update_notif_prefs") as update_mock:
            with self.assertRaises(APIError) as ctx:
                update_member_notification_preferences(
                    user=user,
                    sms_notifications=True,
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.message, "SMS notifications require a valid phone number")
        update_mock.assert_not_called()

    def test_update_member_preferences_returns_email_sms_and_has_phone(self):
        user_id = ObjectId()
        user = {"_id": user_id, "notifPrefs": ["email", "text"], "phone": None}

        with patch("services.member_service.update_notif_prefs") as update_mock:
            response = update_member_notification_preferences(
                user=user,
                email_notifications=True,
            )

        update_mock.assert_called_once()
        self.assertEqual(update_mock.call_args.args[1], ["email"])
        self.assertEqual(
            response,
            {
                "id": str(user_id),
                "emailNotifications": True,
                "smsNotifications": False,
                "hasPhone": False,
                "hasSmsPhone": False,
            },
        )

    def test_update_member_preferences_rejects_sms_when_phone_is_not_e164(self):
        user = {"_id": ObjectId(), "notifPrefs": ["email"], "phone": "4125551234"}

        with patch("services.member_service.update_notif_prefs") as update_mock:
            with self.assertRaises(APIError) as ctx:
                update_member_notification_preferences(
                    user=user,
                    sms_notifications=True,
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.message,
            "SMS notifications require a phone number in E.164 format (for example +15551234567)",
        )
        update_mock.assert_not_called()

    def test_update_member_preferences_returns_has_sms_phone_false_for_naive_phone(self):
        user_id = ObjectId()
        user = {"_id": user_id, "notifPrefs": ["email"], "phone": "4125551234"}

        with patch("services.member_service.update_notif_prefs") as update_mock:
            response = update_member_notification_preferences(
                user=user,
                email_notifications=True,
            )

        update_mock.assert_called_once()
        self.assertEqual(update_mock.call_args.args[1], ["email"])
        self.assertEqual(
            response,
            {
                "id": str(user_id),
                "emailNotifications": True,
                "smsNotifications": False,
                "hasPhone": True,
                "hasSmsPhone": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
