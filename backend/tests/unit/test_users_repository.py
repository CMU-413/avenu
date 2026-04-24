import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from repositories.users_repository import upsert_user_from_external_identity


class UsersRepositoryExternalIdentityTests(unittest.TestCase):
    def test_upsert_user_from_external_identity_creates_new_user_with_default_notification_prefs(self):
        created_user = {"_id": ObjectId(), "optixId": 42, "fullname": "Member User"}

        with patch("repositories.users_repository.find_user_by_optix_id", return_value=None), patch(
            "repositories.users_repository.create_user_with_mailbox",
            return_value=created_user,
        ) as create_mock:
            user_doc, created = upsert_user_from_external_identity(
                optix_id=42,
                fullname="Member User",
                email="member@example.com",
                phone="+15550001111",
                is_admin=False,
                team_ids=[],
            )

        self.assertTrue(created)
        self.assertEqual(user_doc, created_user)
        created_payload = create_mock.call_args.kwargs["user_doc"]
        self.assertEqual(created_payload["notifPrefs"], ["email"])

    def test_upsert_user_from_external_identity_updates_existing_user_without_overwriting_notification_prefs(self):
        user_id = ObjectId()
        team_id = ObjectId()
        existing = {
            "_id": user_id,
            "optixId": 42,
            "fullname": "Old Name",
            "email": "old@example.com",
            "phone": None,
            "isAdmin": False,
            "teamIds": [],
            "notifPrefs": ["text"],
        }
        updated = {**existing, "fullname": "New Name", "email": "new@example.com", "teamIds": [team_id]}

        with patch("repositories.users_repository.find_user_by_optix_id", return_value=existing), patch(
            "repositories.users_repository.update_user_with_mailbox_sync",
            return_value=updated,
        ) as update_mock:
            user_doc, created = upsert_user_from_external_identity(
                optix_id=42,
                fullname="New Name",
                email="new@example.com",
                phone=None,
                is_admin=False,
                team_ids=[team_id],
            )

        self.assertFalse(created)
        self.assertEqual(user_doc, updated)
        patch_payload = update_mock.call_args.kwargs["patch"]
        self.assertEqual(patch_payload["fullname"], "New Name")
        self.assertEqual(patch_payload["email"], "new@example.com")
        self.assertEqual(patch_payload["teamIds"], [team_id])
        self.assertNotIn("notifPrefs", patch_payload)

    def test_upsert_user_from_external_identity_skips_write_when_optix_payload_is_unchanged(self):
        user_id = ObjectId()
        team_id = ObjectId()
        existing = {
            "_id": user_id,
            "optixId": 42,
            "fullname": "Member User",
            "email": "member@example.com",
            "phone": "+15550001111",
            "isAdmin": True,
            "teamIds": [team_id],
            "notifPrefs": ["text"],
        }

        with patch("repositories.users_repository.find_user_by_optix_id", return_value=existing), patch(
            "repositories.users_repository.update_user_with_mailbox_sync"
        ) as update_mock:
            user_doc, created = upsert_user_from_external_identity(
                optix_id=42,
                fullname="Member User",
                email="member@example.com",
                phone="+15550001111",
                is_admin=True,
                team_ids=[team_id],
            )

        self.assertFalse(created)
        self.assertEqual(user_doc, existing)
        update_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
