import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app
from errors import APIError


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
        with patch("controllers.session_controller.find_user_by_email", return_value={"_id": user_id, "isAdmin": True}):
            response = self.client.post("/api/session/login", json={"email": "admin@example.com"})
        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_login_unknown_user_returns_401(self):
        with patch("controllers.session_controller.find_user_by_email", return_value=None):
            response = self.client.post("/api/session/login", json={"email": "missing@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_admin_route_without_session_returns_401(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_admin_route_with_non_admin_user_returns_403(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_route_with_admin_user_succeeds(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}), patch(
            "controllers.users_controller.list_users", return_value=[]
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

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
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

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}), patch(
            "controllers.mail_controller.list_mail", return_value=[]
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

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}):
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
            "controllers.auth_guard.find_user",
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

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": True}):
            response = self.client.get("/api/member/mail?start=2026-02-15&end=2026-02-21")

        self.assertEqual(response.status_code, 403)

    def test_member_mail_requires_range_and_passes_to_service(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = {"start": "2026-02-15", "end": "2026-02-21", "mailboxes": []}
        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.member_controller.list_member_mail_summary", return_value=expected
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
        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.member_controller.update_member_email_notifications", return_value=expected
        ) as prefs_mock:
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, expected)
        prefs_mock.assert_called_once_with(user=user_doc, enabled=True)

    def test_member_preferences_rejects_non_boolean(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": "yes"})

        self.assertEqual(response.status_code, 422)

    def test_member_mail_requests_create_unauthorized_mailbox_returns_403(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.create_mail_request",
            side_effect=APIError(403, "forbidden"),
        ):
            response = self.client.post(
                "/api/mail-requests",
                json={
                    "mailboxId": str(ObjectId()),
                    "expectedSender": "Sender",
                },
            )

        self.assertEqual(response.status_code, 403)

    def test_member_mail_requests_create_validation_failure_missing_text_returns_400(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.create_mail_request",
            side_effect=APIError(400, "expectedSender or description is required"),
        ):
            response = self.client.post(
                "/api/mail-requests",
                json={"mailboxId": str(ObjectId())},
            )

        self.assertEqual(response.status_code, 400)

    def test_member_mail_requests_create_validation_failure_bad_window_returns_400(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.create_mail_request",
            side_effect=APIError(400, "endDate must be on or after startDate"),
        ):
            response = self.client.post(
                "/api/mail-requests",
                json={
                    "mailboxId": str(ObjectId()),
                    "expectedSender": "Sender",
                    "startDate": "2026-02-10",
                    "endDate": "2026-02-09",
                },
            )

        self.assertEqual(response.status_code, 400)

    def test_member_mail_requests_status_filter_defaults_to_active(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = [
            {
                "_id": ObjectId(),
                "memberId": ObjectId(user_id),
                "mailboxId": ObjectId(),
                "expectedSender": "Sender",
                "description": None,
                "startDate": None,
                "endDate": None,
                "status": "ACTIVE",
                "createdAt": datetime(2026, 2, 18, tzinfo=timezone.utc),
                "updatedAt": datetime(2026, 2, 18, tzinfo=timezone.utc),
            }
        ]
        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.list_member_mail_requests",
            return_value=expected,
        ) as list_mock:
            response = self.client.get("/api/mail-requests")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)
        list_mock.assert_called_once_with(user=user_doc, status_filter="ACTIVE")

    def test_member_mail_requests_status_filter_accepts_resolved(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.list_member_mail_requests",
            return_value=[],
        ) as list_mock:
            response = self.client.get("/api/mail-requests?status=RESOLVED")

        self.assertEqual(response.status_code, 200)
        list_mock.assert_called_once_with(user=user_doc, status_filter="RESOLVED")

    def test_member_mail_requests_status_filter_rejects_invalid_value_with_422(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc):
            response = self.client.get("/api/mail-requests?status=NOPE")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json, {"error": "status must be one of ACTIVE, RESOLVED, ALL"})

    def test_member_mail_requests_delete_other_member_returns_404(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        request_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.cancel_member_mail_request",
            side_effect=APIError(404, "mail request not found"),
        ):
            response = self.client.delete(f"/api/mail-requests/{request_id}")

        self.assertEqual(response.status_code, 404)

    def test_member_mail_requests_delete_already_cancelled_returns_404(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "teamIds": []}
        request_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.mail_requests_controller.cancel_member_mail_request",
            side_effect=APIError(404, "mail request not found"),
        ):
            response = self.client.delete(f"/api/mail-requests/{request_id}")

        self.assertEqual(response.status_code, 404)

    def test_admin_mail_requests_list_requires_admin_session(self):
        response = self.client.get("/api/admin/mail-requests")
        self.assertEqual(response.status_code, 401)

    def test_admin_mail_requests_list_accepts_objectid_filters(self):
        session_user_id = str(ObjectId())
        mailbox_id = str(ObjectId())
        member_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.mail_requests_controller.list_admin_active_mail_requests",
            return_value=[],
        ) as list_mock:
            response = self.client.get(f"/api/admin/mail-requests?mailboxId={mailbox_id}&memberId={member_id}")

        self.assertEqual(response.status_code, 200)
        list_mock.assert_called_once_with(mailbox_id=ObjectId(mailbox_id), member_id=ObjectId(member_id))

    def test_admin_mail_requests_list_rejects_invalid_member_id_filter(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}):
            response = self.client.get("/api/admin/mail-requests?memberId=not-object-id")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json, {"error": "memberId must be a valid ObjectId string"})

    def test_admin_resolve_mail_request_requires_admin_session(self):
        response = self.client.post(f"/api/admin/mail-requests/{ObjectId()}/resolve")
        self.assertEqual(response.status_code, 401)

    def test_admin_resolve_mail_request_returns_updated_mail_request_payload(self):
        session_user_id = str(ObjectId())
        request_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        expected = {
            "_id": ObjectId(request_id),
            "memberId": ObjectId(),
            "mailboxId": ObjectId(),
            "status": "RESOLVED",
            "resolvedAt": datetime(2026, 2, 20, tzinfo=timezone.utc),
            "resolvedBy": ObjectId(session_user_id),
            "lastNotificationStatus": "SENT",
            "lastNotificationAt": datetime(2026, 2, 20, tzinfo=timezone.utc),
            "createdAt": datetime(2026, 2, 19, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 2, 20, tzinfo=timezone.utc),
        }
        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.mail_requests_controller.resolve_mail_request_and_notify",
            return_value=expected,
        ) as resolve_mock:
            response = self.client.post(f"/api/admin/mail-requests/{request_id}/resolve")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["id"], request_id)
        self.assertEqual(response.json["status"], "RESOLVED")
        self.assertEqual(response.json["lastNotificationStatus"], "SENT")
        resolve_mock.assert_called_once()
        self.assertEqual(resolve_mock.call_args.kwargs["request_id"], ObjectId(request_id))
        self.assertEqual(resolve_mock.call_args.kwargs["admin_user"]["_id"], ObjectId(session_user_id))

    def test_admin_resolve_mail_request_returns_404_for_resolved_or_cancelled(self):
        session_user_id = str(ObjectId())
        request_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.mail_requests_controller.resolve_mail_request_and_notify",
            side_effect=APIError(404, "mail request not found"),
        ):
            response = self.client.post(f"/api/admin/mail-requests/{request_id}/resolve")

        self.assertEqual(response.status_code, 404)

    def test_admin_retry_notification_requires_admin_session(self):
        response = self.client.post(f"/api/admin/mail-requests/{ObjectId()}/retry-notification")
        self.assertEqual(response.status_code, 401)

    def test_admin_retry_notification_returns_updated_notification_metadata(self):
        session_user_id = str(ObjectId())
        request_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        expected = {
            "_id": ObjectId(request_id),
            "memberId": ObjectId(),
            "mailboxId": ObjectId(),
            "status": "RESOLVED",
            "resolvedAt": datetime(2026, 2, 20, tzinfo=timezone.utc),
            "resolvedBy": ObjectId(session_user_id),
            "lastNotificationStatus": "FAILED",
            "lastNotificationAt": datetime(2026, 2, 21, tzinfo=timezone.utc),
            "createdAt": datetime(2026, 2, 19, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 2, 21, tzinfo=timezone.utc),
        }
        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.mail_requests_controller.retry_mail_request_notification",
            return_value=expected,
        ) as retry_mock:
            response = self.client.post(f"/api/admin/mail-requests/{request_id}/retry-notification")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["id"], request_id)
        self.assertEqual(response.json["lastNotificationStatus"], "FAILED")
        retry_mock.assert_called_once()
        self.assertEqual(retry_mock.call_args.kwargs["request_id"], ObjectId(request_id))

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

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": False}):
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": str(ObjectId()), "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 403)

    def test_admin_weekly_summary_validates_week_range(self):
        session_user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = session_user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}):
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
        provider = object()

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.notifications_controller.build_email_provider",
            return_value=provider,
        ) as provider_factory_mock, patch(
            "controllers.notifications_controller.WeeklySummaryNotifier",
            return_value=notifier,
        ) as notifier_ctor_mock:
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": target_user_id, "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, notify_result)
        provider_factory_mock.assert_called_once_with(testing=True)
        channels = notifier_ctor_mock.call_args.kwargs["channels"]
        self.assertEqual(len(channels), 1)
        self.assertIs(channels[0].provider, provider)
        notifier.notifyWeeklySummary.assert_called_once_with(
            userId=ObjectId(target_user_id),
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

if __name__ == "__main__":
    unittest.main()
