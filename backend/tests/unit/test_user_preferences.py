import os
import unittest

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.user_preferences import normalize_effective_notification_state


class UserPreferencesTests(unittest.TestCase):
    def test_normalize_effective_preferences_merges_current_and_patch(self):
        current_user = {
            "notifPrefs": ["email"],
            "phone": "+15550001111",
        }

        result = normalize_effective_notification_state(
            current_user=current_user,
            sms_notifications_patch=True,
        )

        self.assertEqual(result["notifPrefs"], ["email", "text"])
        self.assertTrue(result["emailNotifications"])
        self.assertTrue(result["smsNotifications"])
        self.assertTrue(result["hasPhone"])

    def test_normalize_effective_preferences_treats_whitespace_phone_as_missing(self):
        current_user = {
            "notifPrefs": ["email", "text"],
            "phone": "   ",
        }

        result = normalize_effective_notification_state(current_user=current_user)

        self.assertEqual(result["notifPrefs"], ["email"])
        self.assertTrue(result["emailNotifications"])
        self.assertFalse(result["smsNotifications"])
        self.assertFalse(result["hasPhone"])

    def test_normalize_effective_preferences_rejects_text_when_explicitly_enabled_without_phone(self):
        current_user = {
            "notifPrefs": [],
            "phone": None,
        }

        with self.assertRaises(APIError) as ctx:
            normalize_effective_notification_state(
                current_user=current_user,
                sms_notifications_patch=True,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.message, "SMS notifications require a valid phone number")


if __name__ == "__main__":
    unittest.main()
