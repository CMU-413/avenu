from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId

from .support import MongoIntegrationTestCase


class NotificationLogPersistenceIntegrationTests(MongoIntegrationTestCase):
    def test_notification_log_writes_are_single_row_and_failure_isolated(self) -> None:
        from config import notification_log_collection
        from repositories.notification_logs_repository import insert_special_case_log, insert_weekly_summary_log

        user_id = ObjectId()
        week_start = date(2026, 2, 16)

        insert_weekly_summary_log(
            user_id=user_id,
            week_start=week_start,
            status="failed",
            reason="all_channels_failed",
            triggered_by="cron",
            error_message="smtp timeout",
            sent_at=None,
        )

        docs_after_failed = list(notification_log_collection.find({"userId": user_id}).sort([("createdAt", 1)]))
        self.assertEqual(len(docs_after_failed), 1)
        failed_doc = docs_after_failed[0]
        self.assertEqual(failed_doc["type"], "weekly-summary")
        self.assertEqual(failed_doc["status"], "failed")
        self.assertEqual(failed_doc["reason"], "all_channels_failed")
        self.assertEqual(failed_doc["triggeredBy"], "cron")
        self.assertEqual(failed_doc["errorMessage"], "smtp timeout")
        self.assertIsNone(failed_doc["sentAt"])
        self.assertIsInstance(failed_doc["createdAt"], datetime)

        insert_special_case_log(
            user_id=user_id,
            status="sent",
            reason=None,
            triggered_by="admin",
            error_message=None,
            sent_at=datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc),
        )

        docs_final = list(notification_log_collection.find({"userId": user_id}).sort([("createdAt", 1)]))
        self.assertEqual(len(docs_final), 2)
        self.assertEqual(docs_final[0]["_id"], failed_doc["_id"])
        self.assertEqual(docs_final[0]["status"], "failed")
        self.assertEqual(docs_final[1]["type"], "special-case")
        self.assertEqual(docs_final[1]["status"], "sent")
        self.assertEqual(docs_final[1]["templateType"], "mail-arrived")
        self.assertIsNotNone(docs_final[1]["sentAt"])
