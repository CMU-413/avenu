import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services import mail_request_service


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, spec):
        docs = list(self._docs)
        for key, direction in reversed(spec):
            reverse = direction < 0
            docs.sort(key=lambda row: row.get(key), reverse=reverse)
        return FakeCursor(docs)

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])
        self.last_update_filter = None

    def insert_one(self, doc):
        created = dict(doc)
        if "_id" not in created:
            created["_id"] = ObjectId()
        self._docs.append(created)
        return SimpleNamespace(inserted_id=created["_id"])

    def find_one(self, query):
        for doc in self._docs:
            if _matches(doc, query):
                return doc
        return None

    def find(self, query):
        return FakeCursor([doc for doc in self._docs if _matches(doc, query)])

    def update_one(self, query, update):
        self.last_update_filter = query
        for doc in self._docs:
            if _matches(doc, query):
                if "$set" in update:
                    for key, value in update["$set"].items():
                        doc[key] = value
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)


def _matches(doc, query):
    for key, value in query.items():
        if isinstance(value, dict) and "$in" in value:
            if doc.get(key) not in value["$in"]:
                return False
            continue
        if doc.get(key) != value:
            return False
    return True


class MailRequestServiceTests(unittest.TestCase):
    def test_create_rejects_unauthorized_mailbox_with_403(self):
        collection = FakeCollection()
        user = {"_id": ObjectId(), "teamIds": []}
        payload = {"mailboxId": str(ObjectId()), "expectedSender": "Sender"}

        with patch.object(mail_request_service, "mail_requests_collection", collection), patch(
            "services.mail_request_service.assert_member_mailbox_access",
            side_effect=APIError(403, "forbidden"),
        ):
            with self.assertRaises(APIError) as ctx:
                mail_request_service.create_mail_request(user=user, payload=payload)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_member_list_returns_only_active_owned_sorted_desc(self):
        member_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 1, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "CANCELLED", "createdAt": datetime(2026, 2, 3, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": ObjectId(), "status": "ACTIVE", "createdAt": datetime(2026, 2, 4, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            docs = mail_request_service.list_member_active_mail_requests(user={"_id": member_id})

        self.assertEqual(len(docs), 2)
        self.assertGreaterEqual(docs[0]["createdAt"], docs[1]["createdAt"])
        self.assertTrue(all(doc["status"] == "ACTIVE" and doc["memberId"] == member_id for doc in docs))

    def test_cancel_soft_deletes_owned_active_request(self):
        member_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection(
            [{"_id": request_id, "memberId": member_id, "status": "ACTIVE", "updatedAt": datetime(2026, 2, 1, tzinfo=timezone.utc)}]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            mail_request_service.cancel_member_mail_request(user={"_id": member_id}, request_id=request_id)

        updated = collection.find_one({"_id": request_id})
        self.assertEqual(updated["status"], "CANCELLED")

    def test_cancel_returns_404_for_missing_foreign_or_already_cancelled_request(self):
        member_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": request_id, "memberId": ObjectId(), "status": "ACTIVE"},
                {"_id": ObjectId(), "memberId": member_id, "status": "CANCELLED"},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            with self.assertRaises(APIError) as ctx:
                mail_request_service.cancel_member_mail_request(user={"_id": member_id}, request_id=request_id)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_cancel_uses_single_atomic_update_with_active_status_guard(self):
        member_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection()

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            with self.assertRaises(APIError):
                mail_request_service.cancel_member_mail_request(user={"_id": member_id}, request_id=request_id)

        self.assertEqual(
            collection.last_update_filter,
            {"_id": request_id, "memberId": member_id, "status": "ACTIVE"},
        )

    def test_admin_list_excludes_cancelled_and_applies_filters(self):
        member_id = ObjectId()
        mailbox_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": ObjectId(), "memberId": member_id, "mailboxId": mailbox_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "mailboxId": mailbox_id, "status": "CANCELLED", "createdAt": datetime(2026, 2, 3, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": ObjectId(), "mailboxId": mailbox_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 4, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            docs = mail_request_service.list_admin_active_mail_requests(member_id=member_id, mailbox_id=mailbox_id)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "ACTIVE")
        self.assertEqual(docs[0]["memberId"], member_id)
        self.assertEqual(docs[0]["mailboxId"], mailbox_id)


if __name__ == "__main__":
    unittest.main()
