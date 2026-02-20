import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class IdentityControllerTests(unittest.TestCase):
    def setUp(self):
        app = create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")
        self.client = app.test_client()

    def test_optix_token_route_requires_token(self):
        response = self.client.post("/api/optix-token", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "Missing token"})

    def test_optix_token_route_returns_created_201(self):
        user_id = ObjectId()
        with patch(
            "controllers.identity_controller.sync_optix_identity",
            return_value=(True, {"_id": user_id, "optixId": 10, "email": "a@example.com"}),
        ):
            response = self.client.post("/api/optix-token", json={"token": "abc"})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["created"])
        self.assertEqual(response.json["user"]["id"], str(user_id))

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_optix_token_route_returns_updated_200(self):
        user_id = ObjectId()
        with patch(
            "controllers.identity_controller.sync_optix_identity",
            return_value=(False, {"_id": user_id, "optixId": 10, "email": "a@example.com"}),
        ):
            response = self.client.post("/api/optix-token", json={"token": "abc"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["created"])
        self.assertEqual(response.json["user"]["id"], str(user_id))


if __name__ == "__main__":
    unittest.main()
