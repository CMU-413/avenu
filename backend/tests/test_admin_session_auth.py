import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class AdminSessionAuthTests(unittest.TestCase):
    def setUp(self):
        app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = app.test_client()

    def test_login_sets_user_id_session(self):
        user_id = ObjectId()
        with patch("app.find_user_by_email", return_value={"_id": user_id, "isAdmin": True}):
            response = self.client.post("/api/session/login", json={"email": "admin@example.com"})
        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_login_unknown_user_returns_401(self):
        with patch("app.find_user_by_email", return_value=None):
            response = self.client.post("/api/session/login", json={"email": "missing@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_admin_route_without_session_returns_401(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_admin_route_with_non_admin_user_returns_403(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_route_with_admin_user_succeeds(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}), patch(
            "app.list_users", return_value=[]
        ):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 200)

    def test_logout_clears_user_id_session(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(ObjectId())

        response = self.client.post("/api/session/logout")
        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_prune_delete_with_non_admin_user_returns_403(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.delete("/api/teams/000000000000000000000000?pruneUsers=true")
        self.assertEqual(response.status_code, 403)

    def test_login_route_is_session_prefixed(self):
        prefixed = self.client.post("/api/session/login", json={})
        self.assertEqual(prefixed.status_code, 422)

        old_admin_login = self.client.post("/api/admin/login", json={})
        self.assertEqual(old_admin_login.status_code, 404)


if __name__ == "__main__":
    unittest.main()
