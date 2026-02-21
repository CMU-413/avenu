import os
import unittest
from datetime import date
from unittest.mock import patch

from pymongo.errors import DuplicateKeyError

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class FakeIdempotencyCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        for existing in self.docs:
            if (
                existing["key"] == doc["key"]
                and existing["route"] == doc["route"]
                and existing["method"] == doc["method"]
            ):
                raise DuplicateKeyError("duplicate")
        self.docs.append(dict(doc))
        return object()

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return object()
        return object()

    def delete_one(self, query):
        self.docs = [
            doc
            for doc in self.docs
            if not all(doc.get(k) == v for k, v in query.items())
        ]
        return object()


class WeeklySummarySchedulerEndpointTests(unittest.TestCase):
    def setUp(self):
        app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = app.test_client()

    def test_scheduler_endpoint_requires_scheduler_token(self):
        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"):
            response = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers={"Idempotency-Key": "weekly-summary:2026-02-09"},
                json={"weekStart": "2026-02-09", "weekEnd": "2026-02-15"},
            )
        self.assertEqual(response.status_code, 401)

    def test_scheduler_endpoint_invokes_weekly_job_runner_once(self):
        idempotency_collection = FakeIdempotencyCollection()
        notifier = object()

        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"), patch(
            "repositories.idempotency_repository.idempotency_keys_collection", idempotency_collection
        ), patch(
            "controllers.internal_jobs_controller.build_notification_channels",
            return_value=[object()],
        ) as channels_builder_mock, patch(
            "controllers.internal_jobs_controller.WeeklySummaryNotifier",
            return_value=notifier,
        ), patch(
            "controllers.internal_jobs_controller.run_weekly_summary_cron_job",
            return_value={
                "weekStart": date(2026, 2, 9),
                "weekEnd": date(2026, 2, 15),
                "processed": 3,
                "sent": 2,
                "skipped": 1,
                "failed": 0,
                "errors": 0,
            },
        ) as job_mock:
            response = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers={
                    "X-Scheduler-Token": "scheduler-secret",
                    "Idempotency-Key": "weekly-summary:2026-02-09",
                },
                json={"weekStart": "2026-02-09", "weekEnd": "2026-02-15"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "weekStart": "2026-02-09",
                "weekEnd": "2026-02-15",
                "processed": 3,
                "sent": 2,
                "skipped": 1,
                "failed": 0,
                "errors": 0,
            },
        )
        job_mock.assert_called_once_with(
            notifier=notifier,
            week_start=date(2026, 2, 9),
            week_end=date(2026, 2, 15),
        )
        channels_builder_mock.assert_called_once_with(testing=True)

    def test_scheduler_endpoint_replays_response_when_idempotency_key_reused(self):
        idempotency_collection = FakeIdempotencyCollection()
        notifier = object()

        with patch("controllers.internal_jobs_controller.SCHEDULER_INTERNAL_TOKEN", "scheduler-secret"), patch(
            "repositories.idempotency_repository.idempotency_keys_collection", idempotency_collection
        ), patch(
            "controllers.internal_jobs_controller.build_notification_channels",
            return_value=[object()],
        ), patch(
            "controllers.internal_jobs_controller.WeeklySummaryNotifier",
            return_value=notifier,
        ), patch(
            "controllers.internal_jobs_controller.run_weekly_summary_cron_job",
            return_value={
                "weekStart": date(2026, 2, 9),
                "weekEnd": date(2026, 2, 15),
                "processed": 1,
                "sent": 1,
                "skipped": 0,
                "failed": 0,
                "errors": 0,
            },
        ) as job_mock:
            headers = {
                "X-Scheduler-Token": "scheduler-secret",
                "Idempotency-Key": "weekly-summary:2026-02-09",
            }
            first = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers=headers,
                json={"weekStart": "2026-02-09", "weekEnd": "2026-02-15"},
            )
            second = self.client.post(
                "/api/internal/jobs/weekly-summary",
                headers=headers,
                json={"weekStart": "2026-02-09", "weekEnd": "2026-02-15"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json, second.json)
        self.assertEqual(job_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
