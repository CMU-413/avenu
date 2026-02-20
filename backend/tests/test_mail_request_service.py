import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


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

    def test_member_list_status_active_returns_active_only(self):
        member_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 1, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "RESOLVED", "createdAt": datetime(2026, 2, 5, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "CANCELLED", "createdAt": datetime(2026, 2, 3, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": ObjectId(), "status": "ACTIVE", "createdAt": datetime(2026, 2, 4, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            docs = mail_request_service.list_member_mail_requests(user={"_id": member_id}, status_filter="ACTIVE")

        self.assertEqual(len(docs), 2)
        self.assertGreaterEqual(docs[0]["createdAt"], docs[1]["createdAt"])
        self.assertTrue(all(doc["status"] == "ACTIVE" and doc["memberId"] == member_id for doc in docs))

    def test_member_list_status_resolved_returns_resolved_only(self):
        member_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 1, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "RESOLVED", "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": ObjectId(), "status": "RESOLVED", "createdAt": datetime(2026, 2, 3, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            docs = mail_request_service.list_member_mail_requests(user={"_id": member_id}, status_filter="RESOLVED")

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "RESOLVED")
        self.assertEqual(docs[0]["memberId"], member_id)

    def test_member_list_status_all_returns_active_and_resolved_only(self):
        member_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": ObjectId(), "memberId": member_id, "status": "ACTIVE", "createdAt": datetime(2026, 2, 1, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "RESOLVED", "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": member_id, "status": "CANCELLED", "createdAt": datetime(2026, 2, 3, tzinfo=timezone.utc)},
                {"_id": ObjectId(), "memberId": ObjectId(), "status": "ACTIVE", "createdAt": datetime(2026, 2, 4, tzinfo=timezone.utc)},
            ]
        )

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            docs = mail_request_service.list_member_mail_requests(user={"_id": member_id}, status_filter="ALL")

        self.assertEqual(len(docs), 2)
        self.assertEqual({doc["status"] for doc in docs}, {"ACTIVE", "RESOLVED"})
        self.assertTrue(all(doc["memberId"] == member_id for doc in docs))

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

    def test_resolve_mail_request_sets_resolved_fields_and_returns_updated_doc(self):
        member_id = ObjectId()
        admin_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection(
            [
                {
                    "_id": request_id,
                    "memberId": member_id,
                    "status": "ACTIVE",
                    "resolvedAt": None,
                    "resolvedBy": None,
                    "lastNotificationStatus": None,
                    "lastNotificationAt": None,
                    "createdAt": datetime(2026, 2, 2, tzinfo=timezone.utc),
                    "updatedAt": datetime(2026, 2, 2, tzinfo=timezone.utc),
                }
            ]
        )
        notifier = Mock()
        notifier.notifySpecialCase.return_value = {"status": "sent", "channelResults": [{"channel": "email", "status": "sent"}]}

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            updated = mail_request_service.resolve_mail_request_and_notify(
                request_id=request_id,
                admin_user={"_id": admin_id},
                notifier=notifier,
            )

        self.assertEqual(updated["status"], "RESOLVED")
        self.assertEqual(updated["resolvedBy"], admin_id)
        self.assertIsNotNone(updated["resolvedAt"])
        self.assertEqual(updated["lastNotificationStatus"], "SENT")
        self.assertIsNotNone(updated["lastNotificationAt"])
        notifier.notifySpecialCase.assert_called_once()
        call_kwargs = notifier.notifySpecialCase.call_args.kwargs
        self.assertEqual(call_kwargs["userId"], member_id)
        self.assertEqual(call_kwargs["triggeredBy"], "admin")
        self.assertEqual(call_kwargs["mailRequest"]["expectedSender"], None)
        self.assertEqual(call_kwargs["mailRequest"]["description"], None)
        self.assertEqual(call_kwargs["mailRequest"]["startDate"], None)
        self.assertEqual(call_kwargs["mailRequest"]["endDate"], None)
        self.assertIsNotNone(call_kwargs["mailRequest"]["resolvedAt"])

    def test_resolve_mail_request_sets_last_notification_failed_metadata_on_failure_without_rollback(self):
        member_id = ObjectId()
        admin_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection(
            [
                {
                    "_id": request_id,
                    "memberId": member_id,
                    "status": "ACTIVE",
                    "resolvedAt": None,
                    "resolvedBy": None,
                    "lastNotificationStatus": None,
                    "lastNotificationAt": None,
                    "updatedAt": datetime(2026, 2, 2, tzinfo=timezone.utc),
                }
            ]
        )
        notifier = Mock()
        notifier.notifySpecialCase.return_value = {
            "status": "failed",
            "reason": "all_channels_failed",
            "channelResults": [{"channel": "email", "status": "failed"}],
        }

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            updated = mail_request_service.resolve_mail_request_and_notify(
                request_id=request_id,
                admin_user={"_id": admin_id},
                notifier=notifier,
            )

        self.assertEqual(updated["status"], "RESOLVED")
        self.assertEqual(updated["lastNotificationStatus"], "FAILED")
        self.assertIsNotNone(updated["lastNotificationAt"])

    def test_resolve_mail_request_returns_404_when_missing_or_not_active(self):
        request_id = ObjectId()
        collection = FakeCollection(
            [
                {"_id": request_id, "memberId": ObjectId(), "status": "CANCELLED"},
                {"_id": ObjectId(), "memberId": ObjectId(), "status": "RESOLVED"},
            ]
        )
        notifier = Mock()

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            with self.assertRaises(APIError) as ctx:
                mail_request_service.resolve_mail_request_and_notify(
                    request_id=request_id,
                    admin_user={"_id": ObjectId()},
                    notifier=notifier,
                )

        self.assertEqual(ctx.exception.status_code, 404)
        notifier.notifySpecialCase.assert_not_called()

    def test_retry_notification_updates_last_notification_metadata_without_lifecycle_change(self):
        member_id = ObjectId()
        request_id = ObjectId()
        resolved_at = datetime(2026, 2, 2, tzinfo=timezone.utc)
        collection = FakeCollection(
            [
                {
                    "_id": request_id,
                    "memberId": member_id,
                    "status": "RESOLVED",
                    "resolvedAt": resolved_at,
                    "resolvedBy": ObjectId(),
                    "lastNotificationStatus": "FAILED",
                    "lastNotificationAt": datetime(2026, 2, 2, 1, tzinfo=timezone.utc),
                    "updatedAt": datetime(2026, 2, 2, 1, tzinfo=timezone.utc),
                }
            ]
        )
        notifier = Mock()
        notifier.notifySpecialCase.return_value = {"status": "sent", "channelResults": [{"channel": "email", "status": "sent"}]}

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            updated = mail_request_service.retry_mail_request_notification(
                request_id=request_id,
                admin_user={"_id": ObjectId()},
                notifier=notifier,
            )

        self.assertEqual(updated["status"], "RESOLVED")
        self.assertEqual(updated["resolvedAt"], resolved_at)
        self.assertEqual(updated["lastNotificationStatus"], "SENT")
        self.assertIsNotNone(updated["lastNotificationAt"])

    def test_retry_notification_returns_404_when_request_missing(self):
        collection = FakeCollection([])
        notifier = Mock()

        with patch.object(mail_request_service, "mail_requests_collection", collection):
            with self.assertRaises(APIError) as ctx:
                mail_request_service.retry_mail_request_notification(
                    request_id=ObjectId(),
                    admin_user={"_id": ObjectId()},
                    notifier=notifier,
                )

        self.assertEqual(ctx.exception.status_code, 404)
        notifier.notifySpecialCase.assert_not_called()

    def test_resolve_mail_request_exception_logs_failure_and_keeps_resolution(self):
        member_id = ObjectId()
        request_id = ObjectId()
        collection = FakeCollection(
            [
                {
                    "_id": request_id,
                    "memberId": member_id,
                    "status": "ACTIVE",
                    "resolvedAt": None,
                    "resolvedBy": None,
                    "lastNotificationStatus": None,
                    "lastNotificationAt": None,
                    "updatedAt": datetime(2026, 2, 2, tzinfo=timezone.utc),
                }
            ]
        )
        notifier = Mock()
        notifier.notifySpecialCase.side_effect = RuntimeError("smtp offline")

        with patch.object(mail_request_service, "mail_requests_collection", collection), patch(
            "services.mail_request_service.insert_special_case_notification_log"
        ) as log_mock:
            updated = mail_request_service.resolve_mail_request_and_notify(
                request_id=request_id,
                admin_user={"_id": ObjectId()},
                notifier=notifier,
            )

        self.assertEqual(updated["status"], "RESOLVED")
        self.assertEqual(updated["lastNotificationStatus"], "FAILED")
        log_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
