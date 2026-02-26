from __future__ import annotations

import os
import unittest

from pymongo import MongoClient
from pymongo.errors import PyMongoError


def _env_bool(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class MongoIntegrationTestCase(unittest.TestCase):
    TEST_DB_NAME = "avenu_db_dev"
    _cleanup_client: MongoClient | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not _env_bool("RUN_MONGO_INTEGRATION"):
            raise unittest.SkipTest("set RUN_MONGO_INTEGRATION=1 to run Mongo integration tests")

        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI must be set for Mongo integration tests")

        db_name = os.getenv("DB_NAME", "avenu_db")
        if db_name != cls.TEST_DB_NAME:
            raise RuntimeError(f"Mongo integration tests require DB_NAME={cls.TEST_DB_NAME}; got {db_name}")

        cls._cleanup_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        try:
            cls._cleanup_client.admin.command("ping")
        except PyMongoError as exc:
            raise RuntimeError(f"failed to connect to Mongo for integration tests: {exc}") from exc

        cls._cleanup_client.drop_database(cls.TEST_DB_NAME)

        # Match production index initialization path.
        from config import ensure_indexes

        ensure_indexes()

