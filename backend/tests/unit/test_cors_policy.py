import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class CorsPolicyTests(unittest.TestCase):
    def test_cors_allows_configured_frontend_origin(self):
        with patch("app.FRONTEND_ORIGINS", ("http://frontend.local:8080",)):
            app = create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")
            client = app.test_client()
            response = client.get("/health", headers={"Origin": "http://frontend.local:8080"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://frontend.local:8080")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_cors_blocks_unconfigured_origin(self):
        with patch("app.FRONTEND_ORIGINS", ("http://frontend.local:8080",)):
            app = create_app(testing=True, ensure_db_indexes_on_startup=False, secret_key="test-secret")
            client = app.test_client()
            response = client.get("/health", headers={"Origin": "http://unknown.local:8080"})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_cors_rejects_wildcard_origin_in_non_testing_mode(self):
        with patch("app.FRONTEND_ORIGINS", ("*",)), patch("app.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"):
            with self.assertRaises(RuntimeError):
                create_app(testing=False, ensure_db_indexes_on_startup=False, secret_key="prod-secret")


if __name__ == "__main__":
    unittest.main()
