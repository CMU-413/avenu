import os
import unittest
from datetime import datetime, timedelta, timezone

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("EMAIL_FROM", "onboarding@resend.dev")

from services.notifications.weekly_summary_cron_job import compute_previous_week_range, run_weekly_summary_cron_job


class FakeUsersCollection:
    def __init__(self, docs):
        self._docs = list(docs)
        self.last_query = None
        self.last_projection = None

    def find(self, query, projection=None):
        self.last_query = query
        self.last_projection = projection
        filtered = []
        for doc in self._docs:
            prefs = doc.get("notifPrefs") or []
            if "email" in prefs:
                filtered.append({"_id": doc["_id"]})
        return filtered


class FakeNotifier:
    def __init__(self, *, raise_on=None, result_by_user=None):
        self.raise_on = set(raise_on or [])
        self.result_by_user = dict(result_by_user or {})
        self.calls = []

    def notifyWeeklySummary(self, *, userId, weekStart, weekEnd, triggeredBy):
        self.calls.append(
            {
                "userId": userId,
                "weekStart": weekStart,
                "weekEnd": weekEnd,
                "triggeredBy": triggeredBy,
            }
        )
        if userId in self.raise_on:
            raise RuntimeError("simulated notifier failure")
        return self.result_by_user.get(userId, {"status": "sent", "channelResults": []})


class FakeLogger:
    def __init__(self):
        self.info_messages = []
        self.error_messages = []
        self.exception_messages = []

    def info(self, msg, *args):
        self.info_messages.append(msg % args if args else msg)

    def error(self, msg, *args):
        self.error_messages.append(msg % args if args else msg)

    def exception(self, msg, *args):
        self.exception_messages.append(msg % args if args else msg)


class WeeklySummaryCronJobTests(unittest.TestCase):
    def test_compute_previous_week_range_uses_deterministic_sunday_to_saturday_window(self):
        now = datetime(2026, 2, 18, 15, 30, tzinfo=timezone.utc)  # Wednesday
        week_start, week_end = compute_previous_week_range(now)
        self.assertEqual(week_start.isoformat(), "2026-02-08")
        self.assertEqual(week_end.isoformat(), "2026-02-14")

    def test_compute_previous_week_range_normalizes_non_utc_input(self):
        now = datetime(2026, 2, 16, 0, 30, tzinfo=timezone(timedelta(hours=14)))  # 2026-02-15T10:30:00Z
        week_start, week_end = compute_previous_week_range(now)
        self.assertEqual(week_start.isoformat(), "2026-02-08")
        self.assertEqual(week_end.isoformat(), "2026-02-14")

    def test_run_weekly_summary_cron_job_fetches_only_opted_in_users(self):
        user_email = ObjectId()
        user_text_only = ObjectId()
        users = FakeUsersCollection(
            [
                {"_id": user_email, "notifPrefs": ["email"]},
                {"_id": user_text_only, "notifPrefs": ["text"]},
            ]
        )
        notifier = FakeNotifier()

        result = run_weekly_summary_cron_job(
            notifier=notifier,
            users=users,
            now=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            logger=FakeLogger(),
        )

        self.assertEqual(users.last_query, {"notifPrefs": {"$in": ["email"]}})
        self.assertEqual(users.last_projection, {"_id": 1})
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]["userId"], user_email)
        self.assertEqual(result["processed"], 1)

    def test_run_weekly_summary_cron_job_passes_cron_trigger_and_week_bounds(self):
        user_id = ObjectId()
        notifier = FakeNotifier()
        users = FakeUsersCollection([{"_id": user_id, "notifPrefs": ["email"]}])

        run_weekly_summary_cron_job(
            notifier=notifier,
            users=users,
            now=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            logger=FakeLogger(),
        )

        self.assertEqual(notifier.calls[0]["triggeredBy"], "cron")
        self.assertEqual(notifier.calls[0]["weekStart"].isoformat(), "2026-02-08")
        self.assertEqual(notifier.calls[0]["weekEnd"].isoformat(), "2026-02-14")

    def test_run_weekly_summary_cron_job_continues_on_notifier_exception(self):
        first = ObjectId()
        second = ObjectId()
        notifier = FakeNotifier(raise_on={first})
        users = FakeUsersCollection(
            [
                {"_id": first, "notifPrefs": ["email"]},
                {"_id": second, "notifPrefs": ["email"]},
            ]
        )
        logger = FakeLogger()

        result = run_weekly_summary_cron_job(
            notifier=notifier,
            users=users,
            now=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            logger=logger,
        )

        self.assertEqual(len(notifier.calls), 2)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(len(logger.exception_messages), 1)
        self.assertIn(str(first), logger.exception_messages[0])

    def test_run_weekly_summary_cron_job_tracks_status_counters(self):
        sent_user = ObjectId()
        skipped_user = ObjectId()
        failed_user = ObjectId()
        users = FakeUsersCollection(
            [
                {"_id": sent_user, "notifPrefs": ["email"]},
                {"_id": skipped_user, "notifPrefs": ["email"]},
                {"_id": failed_user, "notifPrefs": ["email"]},
            ]
        )
        notifier = FakeNotifier(
            result_by_user={
                sent_user: {"status": "sent", "channelResults": []},
                skipped_user: {"status": "skipped", "reason": "already_sent", "channelResults": []},
                failed_user: {"status": "failed", "reason": "all_channels_failed", "channelResults": []},
            }
        )

        result = run_weekly_summary_cron_job(
            notifier=notifier,
            users=users,
            now=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            logger=FakeLogger(),
        )

        self.assertEqual(result["processed"], 3)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"], 0)

    def test_run_weekly_summary_cron_job_logs_start_and_completion(self):
        user_id = ObjectId()
        logger = FakeLogger()

        run_weekly_summary_cron_job(
            notifier=FakeNotifier(),
            users=FakeUsersCollection([{"_id": user_id, "notifPrefs": ["email"]}]),
            now=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            logger=logger,
        )

        self.assertEqual(len(logger.info_messages), 2)
        self.assertIn("weekly_summary_cron_job_start", logger.info_messages[0])
        self.assertIn("weekStart=2026-02-08", logger.info_messages[0])
        self.assertIn("weekly_summary_cron_job_complete", logger.info_messages[1])
        self.assertIn("processed=1", logger.info_messages[1])
        self.assertIn("sent=1", logger.info_messages[1])


if __name__ == "__main__":
    unittest.main()
