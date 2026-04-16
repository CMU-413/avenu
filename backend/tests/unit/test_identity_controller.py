import os
import unittest
from unittest.mock import patch

from bson import ObjectId
from prometheus_client import REGISTRY

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app
from errors import APIError


class IdentityControllerTests(unittest.TestCase):
    def setUp(self):
        app = create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")
        self.client = app.test_client()

    def _sample(self, name: str) -> float:
        v = REGISTRY.get_sample_value(name)
        return 0.0 if v is None else v

    def test_optix_token_route_requires_token(self):
        before_fail = self._sample("autologin_failed_total")
        response = self.client.post("/api/optix-token", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "Missing token"})
        self.assertEqual(self._sample("autologin_failed_total"), before_fail + 1.0)

    def test_optix_token_route_returns_created_201(self):
        user_id = ObjectId()
        before_ok = self._sample("autologin_success_total")
        with patch(
            "controllers.identity_controller.sync_optix_identity",
            return_value=(True, {"_id": user_id, "optixId": 10, "email": "a@example.com"}),
        ):
            response = self.client.post("/api/optix-token", json={"token": "abc"})

        self.assertEqual(self._sample("autologin_success_total"), before_ok + 1.0)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["created"])
        self.assertEqual(response.json["user"]["id"], str(user_id))

        with self.client.session_transaction() as sess:
            self.assertTrue(sess.permanent)
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_optix_token_route_returns_updated_200(self):
        user_id = ObjectId()
        before_ok = self._sample("autologin_success_total")
        with patch(
            "controllers.identity_controller.sync_optix_identity",
            return_value=(False, {"_id": user_id, "optixId": 10, "email": "a@example.com"}),
        ):
            response = self.client.post("/api/optix-token", json={"token": "abc"})

        self.assertEqual(self._sample("autologin_success_total"), before_ok + 1.0)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["created"])
        self.assertEqual(response.json["user"]["id"], str(user_id))

    def test_optix_token_route_increments_failed_on_sync_error(self):
        before_fail = self._sample("autologin_failed_total")
        with patch(
            "controllers.identity_controller.sync_optix_identity",
            side_effect=APIError(502, "upstream"),
        ):
            response = self.client.post("/api/optix-token", json={"token": "abc"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self._sample("autologin_failed_total"), before_fail + 1.0)


if __name__ == "__main__":
    unittest.main()
