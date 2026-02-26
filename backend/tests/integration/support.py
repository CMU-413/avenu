from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
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


class HttpIntegrationTestCase(MongoIntegrationTestCase):
    CLEAN_COLLECTIONS = (
        "mail",
        "mail_requests",
        "notification_log",
        "idempotency_keys",
        "mailboxes",
        "users",
        "teams",
    )
    _optix_counter = 100_000

    def setUp(self) -> None:
        super().setUp()
        if self._cleanup_client is None:
            raise RuntimeError("cleanup client is not initialized")
        db = self._cleanup_client[self.TEST_DB_NAME]
        for collection_name in self.CLEAN_COLLECTIONS:
            db[collection_name].delete_many({})

        from app import create_app

        app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = app.test_client()

    @classmethod
    def _next_optix_id(cls) -> int:
        cls._optix_counter += 1
        return cls._optix_counter

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(tz=timezone.utc)

    def insert_user(
        self,
        *,
        email: str,
        is_admin: bool,
        fullname: str | None = None,
        team_ids: list[ObjectId] | None = None,
        notif_prefs: list[str] | None = None,
        phone: str | None = None,
        user_id: ObjectId | None = None,
        optix_id: int | None = None,
    ) -> dict[str, Any]:
        from repositories.users_repository import insert_user

        now = self._utcnow()
        resolved_id = user_id or ObjectId()
        resolved_fullname = fullname or ("Admin User" if is_admin else "Member User")
        doc: dict[str, Any] = {
            "_id": resolved_id,
            "optixId": optix_id or self._next_optix_id(),
            "isAdmin": is_admin,
            "fullname": resolved_fullname,
            "email": email,
            "phone": phone,
            "teamIds": team_ids or [],
            "notifPrefs": notif_prefs or [],
            "createdAt": now,
            "updatedAt": now,
        }
        insert_user(doc)
        return doc

    def insert_mailbox(
        self,
        *,
        owner_type: str,
        ref_id: ObjectId,
        display_name: str,
    ) -> ObjectId:
        from repositories.mailboxes_repository import insert_mailbox

        now = self._utcnow()
        return insert_mailbox(
            {
                "type": owner_type,
                "refId": ref_id,
                "displayName": display_name,
                "createdAt": now,
                "updatedAt": now,
            }
        )

    def insert_mail_request(
        self,
        *,
        mailbox_id: ObjectId,
        member_id: ObjectId,
        expected_sender: str = "Sender",
        description: str | None = None,
    ) -> dict[str, Any] | None:
        from repositories.mail_requests_repository import create_mail_request

        now = self._utcnow()
        return create_mail_request(
            {
                "mailboxId": mailbox_id,
                "memberId": member_id,
                "expectedSender": expected_sender,
                "description": description,
                "startDate": None,
                "endDate": None,
                "status": "ACTIVE",
                "resolvedAt": None,
                "resolvedBy": None,
                "lastNotificationStatus": None,
                "lastNotificationAt": None,
                "createdAt": now,
                "updatedAt": now,
            }
        )

    def login(self, *, email: str):
        return self.client.post("/api/session/login", json={"email": email})
