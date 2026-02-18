import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("EMAIL_FROM", "onboarding@resend.dev")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


class AdminSessionAuthTests(unittest.TestCase):
    def setUp(self):
        app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = app.test_client()

    def test_login_sets_user_id_session(self):
        user_id = ObjectId()
        with patch("app.find_user_by_email", return_value={"_id": user_id, "isAdmin": True}):
            response = self.client.post("/api/session/login", json={"email": "admin@example.com"})
        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_login_unknown_user_returns_401(self):
        with patch("app.find_user_by_email", return_value=None):
            response = self.client.post("/api/session/login", json={"email": "missing@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_admin_route_without_session_returns_401(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_admin_route_with_non_admin_user_returns_403(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_route_with_admin_user_succeeds(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}), patch(
            "app.list_users", return_value=[]
        ):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 200)

    def test_logout_clears_user_id_session(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(ObjectId())

        response = self.client.post("/api/session/logout")
        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_prune_delete_with_non_admin_user_returns_403(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.delete("/api/teams/000000000000000000000000?pruneUsers=true")
        self.assertEqual(response.status_code, 403)

    def test_login_route_is_session_prefixed(self):
        prefixed = self.client.post("/api/session/login", json={})
        self.assertEqual(prefixed.status_code, 422)

        old_admin_login = self.client.post("/api/admin/login", json={})
        self.assertEqual(old_admin_login.status_code, 404)

    def test_mail_list_without_session_returns_401(self):
        response = self.client.get("/api/mail")
        self.assertEqual(response.status_code, 401)

    def test_mail_list_with_admin_session_accepts_date_and_mailbox_filters(self):
        user_id = str(ObjectId())
        mailbox_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}), patch(
            "app.list_mail", return_value=[]
        ) as list_mail_mock:
            response = self.client.get(f"/api/mail?date=2026-02-17&mailboxId={mailbox_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])
        list_mail_mock.assert_called_once()
        kwargs = list_mail_mock.call_args.kwargs
        self.assertEqual(kwargs["mailbox_id"], ObjectId(mailbox_id))
        self.assertEqual(kwargs["day_start"], datetime(2026, 2, 17, tzinfo=timezone.utc))
        self.assertEqual(kwargs["day_end"], datetime(2026, 2, 18, tzinfo=timezone.utc))

    def test_mail_list_rejects_invalid_date(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}):
            response = self.client.get("/api/mail?date=not-a-date")

        self.assertEqual(response.status_code, 422)

    def test_session_me_requires_session(self):
        response = self.client.get("/api/session/me")
        self.assertEqual(response.status_code, 401)

    def test_session_me_returns_profile(self):
        user_id = str(ObjectId())
        team_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch(
            "auth.find_user",
            return_value={
                "_id": ObjectId(user_id),
                "email": "member@example.com",
                "fullname": "Member User",
                "isAdmin": False,
                "teamIds": [ObjectId(team_id)],
                "notifPrefs": ["email"],
            },
        ):
            response = self.client.get("/api/session/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "id": user_id,
                "email": "member@example.com",
                "fullname": "Member User",
                "isAdmin": False,
                "teamIds": [team_id],
                "emailNotifications": True,
            },
        )

    def test_member_mail_rejects_admin_session(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}):
            response = self.client.get("/api/member/mail?start=2026-02-15&end=2026-02-21")

        self.assertEqual(response.status_code, 403)

    def test_member_mail_requires_range_and_passes_to_service(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = {"start": "2026-02-15", "end": "2026-02-21", "mailboxes": []}
        with patch("auth.find_user", return_value=user_doc), patch(
            "app.list_member_mail_summary", return_value=expected
        ) as member_mail_mock:
            response = self.client.get("/api/member/mail?start=2026-02-15&end=2026-02-21")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, expected)
        member_mail_mock.assert_called_once()
        kwargs = member_mail_mock.call_args.kwargs
        self.assertEqual(kwargs["user"], user_doc)
        self.assertEqual(kwargs["start_day"], datetime(2026, 2, 15, tzinfo=timezone.utc).date())
        self.assertEqual(kwargs["end_day"], datetime(2026, 2, 21, tzinfo=timezone.utc).date())

    def test_member_preferences_patches_boolean_toggle(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "notifPrefs": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = {"id": user_id, "emailNotifications": True}
        with patch("auth.find_user", return_value=user_doc), patch(
            "app.update_member_email_notifications", return_value=expected
        ) as prefs_mock:
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, expected)
        prefs_mock.assert_called_once_with(user=user_doc, enabled=True)

    def test_member_preferences_rejects_non_boolean(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": "yes"})

        self.assertEqual(response.status_code, 422)

    def test_admin_weekly_summary_requires_admin_session(self):
        response = self.client.post(
            "/admin/notifications/summary",
            json={"userId": str(ObjectId()), "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_weekly_summary_rejects_non_admin_session(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": False}):
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": str(ObjectId()), "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 403)

    def test_admin_weekly_summary_validates_week_range(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}):
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": str(ObjectId()), "weekStart": "2026-02-22", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json, {"error": "weekEnd must be on or after weekStart"})

    def test_admin_weekly_summary_calls_notifier_and_returns_result(self):
        session_user_id = str(ObjectId())
        target_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        notify_result = {"status": "sent", "channelResults": [{"channel": "email", "status": "sent"}]}
        notifier = Mock()
        notifier.notifyWeeklySummary.return_value = notify_result

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "app.WeeklySummaryNotifier",
            return_value=notifier,
        ):
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": target_user_id, "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, notify_result)
        notifier.notifyWeeklySummary.assert_called_once_with(
            userId=ObjectId(target_user_id),
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

    def test_admin_special_notification_requires_admin_session(self):
        response = self.client.post(
            "/admin/notifications/special",
            json={"userId": str(ObjectId())},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_special_notification_rejects_non_admin_session(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": False}):
            response = self.client.post(
                "/admin/notifications/special",
                json={"userId": str(ObjectId())},
            )
        self.assertEqual(response.status_code, 403)

    def test_admin_special_notification_requires_user_id(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}):
            response = self.client.post("/admin/notifications/special", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json, {"error": "userId must be a string"})

    def test_admin_special_notification_rejects_invalid_object_ids(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}):
            response = self.client.post(
                "/admin/notifications/special",
                json={"userId": "bad-id"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "invalid user id"})

    def test_admin_special_notification_calls_notifier_and_returns_result(self):
        session_user_id = str(ObjectId())
        target_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        notify_result = {"status": "sent", "channelResults": [{"channel": "email", "status": "sent"}]}
        notifier = Mock()
        notifier.notifySpecialCase.return_value = notify_result

        with patch("auth.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "app.SpecialCaseNotifier",
            return_value=notifier,
        ):
            response = self.client.post(
                "/admin/notifications/special",
                json={"userId": target_user_id},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, notify_result)
        notifier.notifySpecialCase.assert_called_once_with(
            userId=ObjectId(target_user_id),
            triggeredBy="admin",
        )


if __name__ == "__main__":
    unittest.main()
