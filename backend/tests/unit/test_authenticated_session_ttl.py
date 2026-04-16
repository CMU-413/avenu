import os
import unittest
from datetime import timedelta
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class AuthenticatedSessionTTLTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = self.app.test_client()

    def test_app_defaults_authenticated_session_lifetime_to_twelve_hours(self):
        self.assertEqual(self.app.permanent_session_lifetime, timedelta(hours=12))

    def test_permanent_authenticated_session_allows_authenticated_request_within_ttl(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess.permanent = True
            sess["user_id"] = user_id

        with patch(
            "controllers.auth_guard.find_user",
            return_value={"_id": ObjectId(user_id), "isAdmin": True},
        ), patch("controllers.users_controller.list_users", return_value=[]):
            response = self.client.get("/api/users")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_expired_permanent_session_cookie_is_rejected_before_user_lookup(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess.permanent = True
            sess["user_id"] = user_id

        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=-1)

        with patch("controllers.auth_guard.find_user") as find_user_mock:
            response = self.client.get("/api/users")

        self.assertEqual(response.status_code, 401)
        find_user_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
