import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class OcrQueueFeatureFlagTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = self.app.test_client()

    def test_ocr_jobs_returns_404_when_queue_disabled(self):
        with patch("controllers.ocr_queue_controller.FEATURE_OCR_QUEUE_V2", False):
            response = self.client.get("/api/ocr/jobs")
        self.assertEqual(response.status_code, 404)
        body = response.get_json()
        self.assertIsInstance(body, dict)
        self.assertIn("error", body)
