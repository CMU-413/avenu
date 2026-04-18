import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.team_service import delete_team


class TeamServiceTests(unittest.TestCase):
    def test_delete_team_without_prune_propagates_restrict_error(self):
        team_id = ObjectId()

        with patch(
            "services.team_service.delete_team_cascade",
            side_effect=APIError(409, "cannot delete team while users reference it"),
        ):
            with self.assertRaises(APIError) as ctx:
                delete_team(team_id, prune_users=False)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.message, "cannot delete team while users reference it")

    def test_delete_team_with_prune_delegates_to_cascade_delete(self):
        team_id = ObjectId()

        with patch("services.team_service.delete_team_cascade") as delete_mock:
            delete_team(team_id, prune_users=True)

        delete_mock.assert_called_once_with(team_id=team_id, prune_users=True)


if __name__ == "__main__":
    unittest.main()
