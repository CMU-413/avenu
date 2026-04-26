import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.user_service import delete_user, update_user


class UserServiceTests(unittest.TestCase):
    def test_update_user_rejects_text_pref_when_effective_phone_missing(self):
        user_id = ObjectId()

        with patch(
            "services.user_service.find_user",
            return_value={"_id": user_id, "notifPrefs": [], "phone": None},
        ), patch(
            "services.user_service.build_user_patch",
            return_value={"notifPrefs": ["text"]},
        ):
            with self.assertRaises(APIError) as ctx:
                update_user(user_id, payload={"notifPrefs": ["text"]})

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.message, "SMS notifications require a valid phone number")

    def test_update_user_rejects_text_pref_when_phone_is_not_e164(self):
        user_id = ObjectId()

        with patch(
            "services.user_service.find_user",
            return_value={"_id": user_id, "notifPrefs": [], "phone": "4125551234"},
        ), patch(
            "services.user_service.build_user_patch",
            return_value={"notifPrefs": ["text"]},
        ):
            with self.assertRaises(APIError) as ctx:
                update_user(user_id, payload={"notifPrefs": ["text"]})

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.message,
            "SMS notifications require a phone number in E.164 format (for example +15551234567)",
        )

    def test_update_user_auto_removes_text_pref_when_phone_patched_to_non_e164(self):
        user_id = ObjectId()
        current = {"_id": user_id, "notifPrefs": ["email", "text"], "phone": "+15550001111"}
        persisted = {"_id": user_id, "notifPrefs": ["email"], "phone": "4125551234"}

        with patch("services.user_service.find_user", return_value=current), patch(
            "services.user_service.build_user_patch",
            return_value={"phone": "4125551234"},
        ), patch(
            "services.user_service.update_user_with_mailbox_sync",
            return_value=persisted,
        ) as update_mock:
            response = update_user(user_id, payload={"phone": "4125551234"})

        self.assertEqual(response, persisted)
        self.assertEqual(update_mock.call_args.kwargs["patch"]["phone"], "4125551234")
        self.assertEqual(update_mock.call_args.kwargs["patch"]["notifPrefs"], ["email"])

    def test_update_user_auto_removes_text_pref_when_phone_cleared(self):
        user_id = ObjectId()
        current = {"_id": user_id, "notifPrefs": ["email", "text"], "phone": "+15550001111"}
        persisted = {"_id": user_id, "notifPrefs": ["email"], "phone": None}

        with patch("services.user_service.find_user", return_value=current), patch(
            "services.user_service.build_user_patch",
            return_value={"phone": None},
        ), patch(
            "services.user_service.update_user_with_mailbox_sync",
            return_value=persisted,
        ) as update_mock:
            response = update_user(user_id, payload={"phone": ""})

        self.assertEqual(response, persisted)
        self.assertEqual(update_mock.call_args.kwargs["patch"]["phone"], None)
        self.assertEqual(update_mock.call_args.kwargs["patch"]["notifPrefs"], ["email"])

    def test_delete_user_delegates_to_cascade_delete(self):
        user_id = ObjectId()

        with patch("services.user_service.delete_user_cascade") as delete_mock:
            delete_user(user_id)

        delete_mock.assert_called_once_with(user_id)


if __name__ == "__main__":
    unittest.main()
