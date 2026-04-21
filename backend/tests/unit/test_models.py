import unittest

from bson import ObjectId

from errors import APIError
from models import (
    MAIL_REQUEST_NOTIFICATION_STATUSES,
    MAIL_REQUEST_STATUSES,
    build_mail_create,
    build_mail_patch,
    build_mail_request_create,
    build_user_create,
)


class ModelBuilderTests(unittest.TestCase):
    def test_build_user_create_sets_defaults(self):
        payload = {
            "optixId": 10,
            "fullname": "Jane Doe",
            "email": "Jane@Example.com",
        }
        doc = build_user_create(payload)
        self.assertEqual(doc["email"], "jane@example.com")
        self.assertFalse(doc["isAdmin"])
        self.assertEqual(doc["teamIds"], [])

    def test_build_user_create_requires_fullname(self):
        with self.assertRaises(APIError):
            build_user_create({"optixId": 1, "email": "a@b.com"})

    def test_build_mail_create_validates(self):
        payload = {
            "mailboxId": str(ObjectId()),
            "date": "2025-01-01T10:00:00Z",
            "type": "letter",
            "receiverName": "Acme Corp",
        }
        doc = build_mail_create(payload)
        self.assertEqual(doc["type"], "letter")
        self.assertEqual(doc["receiverName"], "Acme Corp")
        self.assertNotIn("count", doc)

    def test_build_mail_create_never_writes_legacy_count(self):
        """New writes are always one-doc-per-piece; service layer expands count."""
        mb = str(ObjectId())
        doc_one = build_mail_create(
            {"mailboxId": mb, "date": "2025-01-01T10:00:00Z", "type": "letter", "count": 1}
        )
        self.assertNotIn("count", doc_one)
        doc_many = build_mail_create(
            {"mailboxId": mb, "date": "2025-01-01T10:00:00Z", "type": "package", "count": 12}
        )
        self.assertNotIn("count", doc_many)

    def test_build_mail_create_rejects_bad_type(self):
        with self.assertRaises(APIError):
            build_mail_create(
                {
                    "mailboxId": str(ObjectId()),
                    "date": "2025-01-01T10:00:00Z",
                    "type": "postcard",
                }
            )

    def test_build_mail_patch_count_gt_one(self):
        patch = build_mail_patch(
            {"date": "2025-01-01T12:00:00Z", "count": 7},
        )
        self.assertEqual(patch["count"], 7)
        self.assertIn("updatedAt", patch)

    def test_build_mail_patch_omits_count_when_one(self):
        patch = build_mail_patch(
            {"date": "2025-01-01T12:00:00Z", "count": 1},
        )
        self.assertNotIn("count", patch)

    def test_build_mail_create_omits_is_promotional_when_absent(self):
        doc = build_mail_create(
            {
                "mailboxId": str(ObjectId()),
                "date": "2025-01-01T10:00:00Z",
                "type": "letter",
            }
        )
        self.assertNotIn("isPromotional", doc)

    def test_build_mail_create_sets_is_promotional_true(self):
        doc = build_mail_create(
            {
                "mailboxId": str(ObjectId()),
                "date": "2025-01-01T10:00:00Z",
                "type": "letter",
                "isPromotional": True,
            }
        )
        self.assertIs(doc["isPromotional"], True)

    def test_build_mail_create_omits_is_promotional_when_false(self):
        doc = build_mail_create(
            {
                "mailboxId": str(ObjectId()),
                "date": "2025-01-01T10:00:00Z",
                "type": "letter",
                "isPromotional": False,
            }
        )
        self.assertNotIn("isPromotional", doc)

    def test_build_mail_create_rejects_non_bool_is_promotional(self):
        with self.assertRaises(APIError):
            build_mail_create(
                {
                    "mailboxId": str(ObjectId()),
                    "date": "2025-01-01T10:00:00Z",
                    "type": "letter",
                    "isPromotional": "yes",
                }
            )

    def test_build_mail_patch_sets_is_promotional_true(self):
        patch = build_mail_patch({"isPromotional": True})
        self.assertIs(patch["isPromotional"], True)

    def test_build_mail_patch_sets_is_promotional_false(self):
        patch = build_mail_patch({"isPromotional": False})
        self.assertIs(patch["isPromotional"], False)

    def test_build_mail_patch_rejects_non_bool_is_promotional(self):
        with self.assertRaises(APIError):
            build_mail_patch({"isPromotional": 1})

    def test_build_mail_request_create_requires_expected_sender_or_description(self):
        with self.assertRaises(APIError) as ctx:
            build_mail_request_create(
                {"mailboxId": str(ObjectId())},
                member_id=ObjectId(),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_build_mail_request_create_rejects_end_before_start(self):
        with self.assertRaises(APIError) as ctx:
            build_mail_request_create(
                {
                    "mailboxId": str(ObjectId()),
                    "expectedSender": "Sender",
                    "startDate": "2026-02-10",
                    "endDate": "2026-02-09",
                },
                member_id=ObjectId(),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_build_mail_request_create_sets_member_status_and_timestamps(self):
        member_id = ObjectId()
        payload = {
            "mailboxId": str(ObjectId()),
            "expectedSender": "Sender Inc",
            "description": "Important package",
            "startDate": "2026-02-10",
            "endDate": "2026-02-15",
        }
        doc = build_mail_request_create(payload, member_id=member_id)

        self.assertEqual(doc["memberId"], member_id)
        self.assertEqual(doc["status"], "ACTIVE")
        self.assertIsNone(doc["resolvedAt"])
        self.assertIsNone(doc["resolvedBy"])
        self.assertIsNone(doc["lastNotificationStatus"])
        self.assertIsNone(doc["lastNotificationAt"])
        self.assertEqual(doc["startDate"], "2026-02-10")
        self.assertEqual(doc["endDate"], "2026-02-15")
        self.assertIsNotNone(doc["createdAt"])
        self.assertIsNotNone(doc["updatedAt"])

    def test_mail_request_status_enum_includes_resolved(self):
        self.assertEqual(MAIL_REQUEST_STATUSES, {"ACTIVE", "CANCELLED", "RESOLVED"})

    def test_mail_request_notification_status_enum(self):
        self.assertEqual(MAIL_REQUEST_NOTIFICATION_STATUSES, {"SENT", "SKIPPED", "FAILED"})


if __name__ == "__main__":
    unittest.main()
