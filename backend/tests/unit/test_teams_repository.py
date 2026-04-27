import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from repositories.teams_repository import ensure_team_from_external_identity


class TeamsRepositoryExternalIdentityTests(unittest.TestCase):
    def test_ensure_team_from_external_identity_creates_new_team_when_missing(self):
        created_team = {"_id": ObjectId(), "optixId": 99, "name": "Team One"}

        with patch("repositories.teams_repository.find_team_by_optix_id", return_value=None), patch(
            "repositories.teams_repository.create_team_with_mailbox",
            return_value=created_team,
        ) as create_mock:
            team_doc = ensure_team_from_external_identity(optix_id=99, name="Team One")

        self.assertEqual(team_doc, created_team)
        self.assertEqual(create_mock.call_args.kwargs["team_doc"]["name"], "Team One")

    def test_ensure_team_from_external_identity_refreshes_existing_team_name_when_changed(self):
        team_id = ObjectId()
        existing = {"_id": team_id, "optixId": 99, "name": "Old Team"}
        updated = {"_id": team_id, "optixId": 99, "name": "New Team"}

        with patch("repositories.teams_repository.find_team_by_optix_id", return_value=existing), patch(
            "repositories.teams_repository.update_team_with_mailbox_sync",
            return_value=updated,
        ) as update_mock:
            team_doc = ensure_team_from_external_identity(optix_id=99, name="New Team")

        self.assertEqual(team_doc, updated)
        patch_payload = update_mock.call_args.kwargs["patch"]
        self.assertEqual(patch_payload["name"], "New Team")
        self.assertIn("updatedAt", patch_payload)

    def test_ensure_team_from_external_identity_skips_write_when_team_name_is_unchanged(self):
        team_id = ObjectId()
        existing = {"_id": team_id, "optixId": 99, "name": "Team One"}

        with patch("repositories.teams_repository.find_team_by_optix_id", return_value=existing), patch(
            "repositories.teams_repository.update_team_with_mailbox_sync"
        ) as update_mock:
            team_doc = ensure_team_from_external_identity(optix_id=99, name="Team One")

        self.assertEqual(team_doc, existing)
        update_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
