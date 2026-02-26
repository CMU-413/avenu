import os
import unittest
from unittest.mock import patch

from bson import ObjectId
from requests import Timeout

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.identity_sync_service import check_optix_health, sync_optix_identity


class FakeResponse:
    def __init__(self, *, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class IdentitySyncServiceTests(unittest.TestCase):
    def test_check_optix_health_returns_misconfigured_when_token_missing(self):
        status = check_optix_health(token="", timeout_seconds=0.1)
        self.assertEqual(status, "misconfigured")

    def test_check_optix_health_returns_healthy_on_200(self):
        with patch(
            "services.identity_sync_service.requests.post",
            return_value=FakeResponse(status_code=200, payload={"data": {}}),
        ):
            status = check_optix_health(token="optix-token", timeout_seconds=0.1)

        self.assertEqual(status, "healthy")

    def test_check_optix_health_returns_unreachable_on_timeout(self):
        with patch("services.identity_sync_service.requests.post", side_effect=Timeout("timeout")):
            status = check_optix_health(token="optix-token", timeout_seconds=0.1)

        self.assertEqual(status, "unreachable")

    def test_sync_optix_identity_creates_new_user_and_team(self):
        user_id = ObjectId()
        team_id = ObjectId()

        with patch(
            "services.identity_sync_service.requests.post",
            return_value=FakeResponse(
                status_code=200,
                payload={
                    "data": {
                        "me": {
                            "user": {
                                "user_id": 123,
                                "email": "member@example.com",
                                "name": "Member User",
                                "is_admin": False,
                                "teams": [{"team_id": 99, "name": "Team One"}],
                            }
                        }
                    }
                },
            ),
        ), patch(
            "services.identity_sync_service.ensure_team_from_external_identity",
            return_value={"_id": team_id, "optixId": 99, "name": "Team One"},
        ) as ensure_team_mock, patch(
            "services.identity_sync_service.upsert_user_from_external_identity",
            return_value=({"_id": user_id, "optixId": 123, "email": "member@example.com"}, True),
        ) as upsert_user_mock:
            created, user_doc = sync_optix_identity(token="optix-token")

        self.assertTrue(created)
        self.assertEqual(user_doc["_id"], user_id)
        ensure_team_mock.assert_called_once_with(optix_id=99, name="Team One")
        upsert_user_mock.assert_called_once()
        kwargs = upsert_user_mock.call_args.kwargs
        self.assertEqual(kwargs["optix_id"], 123)
        self.assertEqual(kwargs["team_ids"], [team_id])

    def test_sync_optix_identity_updates_existing_user(self):
        user_id = ObjectId()

        with patch(
            "services.identity_sync_service.requests.post",
            return_value=FakeResponse(
                status_code=200,
                payload={
                    "data": {
                        "me": {
                            "user": {
                                "user_id": 123,
                                "email": "member@example.com",
                                "name": "Updated Name",
                                "is_admin": True,
                                "teams": [],
                            }
                        }
                    }
                },
            ),
        ), patch(
            "services.identity_sync_service.upsert_user_from_external_identity",
            return_value=({"_id": user_id, "optixId": 123, "email": "member@example.com"}, False),
        ):
            created, user_doc = sync_optix_identity(token="optix-token")

        self.assertFalse(created)
        self.assertEqual(user_doc["_id"], user_id)

    def test_sync_optix_identity_raises_on_optix_failure_and_does_not_write_local_state(self):
        with patch(
            "services.identity_sync_service.requests.post",
            return_value=FakeResponse(status_code=503, payload={}),
        ), patch("services.identity_sync_service.ensure_team_from_external_identity") as ensure_team_mock, patch(
            "services.identity_sync_service.upsert_user_from_external_identity"
        ) as upsert_user_mock:
            with self.assertRaises(APIError) as ctx:
                sync_optix_identity(token="optix-token")

        self.assertEqual(ctx.exception.status_code, 503)
        ensure_team_mock.assert_not_called()
        upsert_user_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
