import os
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from repositories.login_rate_limit_repository import record_login_attempt


class _FakeCollection:
    def __init__(self):
        self.docs = []

    def find_one_and_update(self, query, update, *, upsert=False, return_document=None):
        del return_document
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                for key, value in update.get("$inc", {}).items():
                    doc[key] = doc.get(key, 0) + value
                for key, value in update.get("$set", {}).items():
                    doc[key] = deepcopy(value)
                return deepcopy(doc)

        if not upsert:
            return None

        doc = deepcopy(query)
        for key, value in update.get("$setOnInsert", {}).items():
            doc[key] = deepcopy(value)
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value
        for key, value in update.get("$set", {}).items():
            doc[key] = deepcopy(value)
        self.docs.append(doc)
        return deepcopy(doc)


class LoginRateLimitRepositoryTests(unittest.TestCase):
    def test_record_attempt_increments_existing_bucket(self):
        collection = _FakeCollection()
        now = datetime(2026, 4, 8, 16, 30, tzinfo=timezone.utc)

        with patch("repositories.login_rate_limit_repository.login_rate_limit_collection", collection):
            first = record_login_attempt(scope="ip", key="203.0.113.8", window_seconds=60, now=now)
            second = record_login_attempt(scope="ip", key="203.0.113.8", window_seconds=60, now=now + timedelta(seconds=10))

        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 2)
        self.assertEqual(second["scope"], "ip")
        self.assertEqual(second["key"], "203.0.113.8")
        self.assertEqual(second["windowStart"], now)

    def test_record_attempt_starts_new_bucket_after_window_boundary(self):
        collection = _FakeCollection()
        now = datetime(2026, 4, 8, 16, 30, 45, tzinfo=timezone.utc)

        with patch("repositories.login_rate_limit_repository.login_rate_limit_collection", collection):
            first = record_login_attempt(scope="email", key="admin@example.com", window_seconds=60, now=now)
            second = record_login_attempt(
                scope="email",
                key="admin@example.com",
                window_seconds=60,
                now=now + timedelta(seconds=20),
            )

        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 1)
        self.assertNotEqual(first["windowStart"], second["windowStart"])

    def test_record_attempt_isolated_by_scope_and_key(self):
        collection = _FakeCollection()
        now = datetime(2026, 4, 8, 16, 30, tzinfo=timezone.utc)

        with patch("repositories.login_rate_limit_repository.login_rate_limit_collection", collection):
            ip_bucket = record_login_attempt(scope="ip", key="203.0.113.8", window_seconds=60, now=now)
            email_bucket = record_login_attempt(scope="email", key="admin@example.com", window_seconds=900, now=now)
            other_ip_bucket = record_login_attempt(scope="ip", key="203.0.113.9", window_seconds=60, now=now)

        self.assertEqual(ip_bucket["count"], 1)
        self.assertEqual(email_bucket["count"], 1)
        self.assertEqual(other_ip_bucket["count"], 1)
        self.assertEqual(len(collection.docs), 3)


if __name__ == "__main__":
    unittest.main()
