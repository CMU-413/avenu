import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import request as flask_request

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app
from controllers.session_rate_limit import evaluate_login_rate_limit
from errors import APIError
from services.notifications.providers.email_provider import MailProviderError


class AdminSessionAuthTests(unittest.TestCase):
    def setUp(self):
        app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = app.test_client()

    def _allow_login_rate_limit(self):
        def fake_record_login_attempt(*, scope, key, window_seconds, now=None):
            del scope, key, window_seconds, now
            return {
                "count": 1,
                "windowSeconds": 60,
                "windowStart": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "expiresAt": datetime(2026, 4, 8, 16, 15, tzinfo=timezone.utc),
                "createdAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "updatedAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            }

        return patch("controllers.session_rate_limit.record_login_attempt", side_effect=fake_record_login_attempt)

    def test_login_request_for_admin_sends_magic_link_and_does_not_set_session(self):
        user_id = ObjectId()
        magic_link_service = Mock()
        magic_link_service.link_expiry_seconds = 900
        magic_link_service.generate_admin_login_link.return_value = "https://hub.avenuworkspaces.com/mail/?token_id=abc&signature=def"
        email_provider = Mock()

        with patch(
            "controllers.session_controller.find_user_by_email",
            return_value={"_id": user_id, "isAdmin": True, "email": "admin@example.com", "fullname": "Admin User"},
        ), patch(
            "controllers.session_controller.AuthMagicLinkService",
            return_value=magic_link_service,
        ), patch(
            "controllers.session_controller.build_email_provider",
            return_value=email_provider,
        ), self._allow_login_rate_limit():
            response = self.client.post("/api/session/login", json={"email": "admin@example.com"})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json, {"status": "ok"})
        magic_link_service.generate_admin_login_link.assert_called_once()
        email_provider.send.assert_called_once()
        send_kwargs = email_provider.send.call_args.kwargs
        self.assertEqual(send_kwargs["to"], "admin@example.com")
        self.assertIn('href="https://hub.avenuworkspaces.com/mail/?token_id=abc&amp;signature=def"', send_kwargs["html"])

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    def test_login_unknown_user_returns_generic_success(self):
        with patch("controllers.session_controller.find_user_by_email", return_value=None), self._allow_login_rate_limit():
            response = self.client.post("/api/session/login", json={"email": "missing@example.com"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json, {"status": "ok"})

    def test_login_non_admin_user_returns_generic_success_without_sending_email(self):
        email_provider = Mock()

        with patch(
            "controllers.session_controller.find_user_by_email",
            return_value={"_id": ObjectId(), "isAdmin": False, "email": "member@example.com"},
        ), patch(
            "controllers.session_controller.build_email_provider",
            return_value=email_provider,
        ), self._allow_login_rate_limit():
            response = self.client.post("/api/session/login", json={"email": "member@example.com"})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json, {"status": "ok"})
        email_provider.send.assert_not_called()

    def test_login_request_returns_503_when_email_delivery_fails(self):
        magic_link_service = Mock()
        magic_link_service.link_expiry_seconds = 900
        magic_link_service.generate_admin_login_link.return_value = "https://hub.avenuworkspaces.com/mail/?token_id=abc&signature=def"
        email_provider = Mock()
        email_provider.send.side_effect = MailProviderError("provider failed")

        with patch(
            "controllers.session_controller.find_user_by_email",
            return_value={"_id": ObjectId(), "isAdmin": True, "email": "admin@example.com", "fullname": "Admin User"},
        ), patch(
            "controllers.session_controller.AuthMagicLinkService",
            return_value=magic_link_service,
        ), patch(
            "controllers.session_controller.build_email_provider",
            return_value=email_provider,
        ), self._allow_login_rate_limit():
            response = self.client.post("/api/session/login", json={"email": "admin@example.com"})

        self.assertEqual(response.status_code, 503)

    def test_login_rate_limit_allows_request_when_counts_are_below_threshold(self):
        recorded = []
        app = self.client.application

        def fake_record_login_attempt(*, scope, key, window_seconds, now=None):
            del now
            recorded.append((scope, key, window_seconds))
            return {
                "scope": scope,
                "key": key,
                "count": 1,
                "windowSeconds": window_seconds,
                "windowStart": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "expiresAt": datetime(2026, 4, 8, 16, 15, tzinfo=timezone.utc),
                "createdAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "updatedAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            }

        with app.test_request_context(
            "/api/session/login",
            method="POST",
            json={"email": " Admin@Example.com "},
            headers={"X-Forwarded-For": "203.0.113.8, 10.0.0.1"},
        ), patch("controllers.session_rate_limit.record_login_attempt", side_effect=fake_record_login_attempt):
            decision = evaluate_login_rate_limit(
                request=flask_request,
                payload={"email": " Admin@Example.com "},
            )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.client_ip, "203.0.113.8")
        self.assertEqual(decision.email, "admin@example.com")
        self.assertEqual(
            recorded,
            [
                ("ip", "203.0.113.8", decision.ip.window_seconds),
                ("email", "admin@example.com", decision.email_scope.window_seconds),
            ],
        )

    def test_login_request_throttles_per_ip_without_calling_magic_link_sender(self):
        counts = {}
        magic_link_service = Mock()
        magic_link_service.link_expiry_seconds = 900
        magic_link_service.generate_admin_login_link.return_value = "https://hub.avenuworkspaces.com/mail/?token_id=abc&signature=def"
        email_provider = Mock()

        def fake_record_login_attempt(*, scope, key, window_seconds, now=None):
            del window_seconds, now
            bucket_key = (scope, key)
            counts[bucket_key] = counts.get(bucket_key, 0) + 1
            return {
                "scope": scope,
                "key": key,
                "count": counts[bucket_key],
                "windowSeconds": 60 if scope == "ip" else 900,
                "windowStart": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "expiresAt": datetime(2026, 4, 8, 16, 15, tzinfo=timezone.utc),
                "createdAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "updatedAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            }

        with patch(
            "controllers.session_rate_limit.record_login_attempt",
            side_effect=fake_record_login_attempt,
        ), patch(
            "controllers.session_controller.find_user_by_email",
            side_effect=lambda email: {"_id": ObjectId(), "isAdmin": True, "email": email, "fullname": "Admin User"},
        ), patch(
            "controllers.session_controller.AuthMagicLinkService",
            return_value=magic_link_service,
        ), patch(
            "controllers.session_controller.build_email_provider",
            return_value=email_provider,
        ), patch(
            "controllers.session_controller.logger.warning",
        ) as warning_log:
            responses = []
            for idx in range(6):
                responses.append(
                    self.client.post(
                        "/api/session/login",
                        json={"email": f"admin{idx}@example.com"},
                        headers={"X-Forwarded-For": "203.0.113.8"},
                    )
                )

        self.assertEqual([response.status_code for response in responses], [202, 202, 202, 202, 202, 202])
        self.assertEqual([response.json for response in responses], [{"status": "ok"}] * 6)
        self.assertEqual(magic_link_service.generate_admin_login_link.call_count, 5)
        self.assertEqual(email_provider.send.call_count, 5)
        warning_log.assert_called_once()
        warning_kwargs = warning_log.call_args.kwargs
        self.assertEqual(warning_kwargs["extra"]["throttled_scopes"], ["ip"])
        self.assertEqual(warning_kwargs["extra"]["client_ip"], "203.0.113.8")
        self.assertEqual(warning_kwargs["extra"]["ip_count"], 6)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    def test_login_request_throttles_per_email_for_unknown_user_and_logs_warning(self):
        counts = {}

        def fake_record_login_attempt(*, scope, key, window_seconds, now=None):
            del window_seconds, now
            bucket_key = (scope, key)
            counts[bucket_key] = counts.get(bucket_key, 0) + 1
            return {
                "scope": scope,
                "key": key,
                "count": counts[bucket_key],
                "windowSeconds": 60 if scope == "ip" else 900,
                "windowStart": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "expiresAt": datetime(2026, 4, 8, 16, 15, tzinfo=timezone.utc),
                "createdAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
                "updatedAt": datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            }

        with patch(
            "controllers.session_rate_limit.record_login_attempt",
            side_effect=fake_record_login_attempt,
        ), patch(
            "controllers.session_controller.find_user_by_email",
            return_value=None,
        ), patch(
            "controllers.session_controller.AuthMagicLinkService",
        ) as auth_magic_link_service_cls, patch(
            "controllers.session_controller.build_email_provider",
        ) as build_email_provider, patch(
            "controllers.session_controller.logger.warning",
        ) as warning_log:
            responses = []
            for idx in range(6):
                responses.append(
                    self.client.post(
                        "/api/session/login",
                        json={"email": " Admin@Example.com "},
                        headers={"X-Forwarded-For": f"203.0.113.{idx}"},
                    )
                )

        self.assertEqual([response.status_code for response in responses], [202, 202, 202, 202, 202, 202])
        self.assertEqual([response.json for response in responses], [{"status": "ok"}] * 6)
        auth_magic_link_service_cls.assert_not_called()
        build_email_provider.assert_not_called()
        warning_log.assert_called_once()
        warning_kwargs = warning_log.call_args.kwargs
        self.assertEqual(warning_kwargs["extra"]["throttled_scopes"], ["email"])
        self.assertEqual(warning_kwargs["extra"]["email_count"], 6)
        self.assertEqual(warning_kwargs["extra"]["email_key"], "admin@example.com")

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

    def test_session_redeem_sets_user_id_session(self):
        user_id = ObjectId()
        with patch(
            "controllers.session_controller.AuthMagicLinkService",
        ) as auth_magic_link_service_cls, patch(
            "controllers.session_controller.get_user",
            return_value={"_id": user_id, "isAdmin": True},
        ):
            auth_magic_link_service_cls.return_value.verify_login_link.return_value = {"userId": user_id}
            response = self.client.post("/api/session/redeem", json={"tokenId": "token-123", "signature": "signed"})

        self.assertEqual(response.status_code, 204)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), str(user_id))

    def test_session_redeem_unknown_or_non_admin_user_returns_401(self):
        user_id = ObjectId()
        with patch(
            "controllers.session_controller.AuthMagicLinkService",
        ) as auth_magic_link_service_cls, patch(
            "controllers.session_controller.get_user",
            return_value={"_id": user_id, "isAdmin": False},
        ):
            auth_magic_link_service_cls.return_value.verify_login_link.return_value = {"userId": user_id}
            response = self.client.post("/api/session/redeem", json={"tokenId": "token-123", "signature": "signed"})

        self.assertEqual(response.status_code, 401)

    def test_session_redeem_accepts_long_signature_payload(self):
        user_id = ObjectId()
        long_signature = "signed." + ("x" * 600)
        with patch(
            "controllers.session_controller.AuthMagicLinkService",
        ) as auth_magic_link_service_cls, patch(
            "controllers.session_controller.get_user",
            return_value={"_id": user_id, "isAdmin": True},
        ):
            auth_magic_link_service_cls.return_value.verify_login_link.return_value = {"userId": user_id}
            response = self.client.post(
                "/api/session/redeem",
                json={"tokenId": "token-123", "signature": long_signature},
            )

        self.assertEqual(response.status_code, 204)

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
                "phone": "+15550001111",
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
                "smsNotifications": False,
                "hasPhone": True,
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
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "notifPrefs": [], "phone": "+15550001111"}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = {"id": user_id, "emailNotifications": True, "smsNotifications": False, "hasPhone": True}
        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.member_controller.update_member_notification_preferences", return_value=expected
        ) as prefs_mock:
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, expected)
        prefs_mock.assert_called_once()
        self.assertEqual(prefs_mock.call_args.kwargs["user"], user_doc)
        self.assertEqual(prefs_mock.call_args.kwargs["email_notifications"], True)

    def test_member_preferences_rejects_non_boolean(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.patch("/api/member/preferences", json={"emailNotifications": "yes"})

        self.assertEqual(response.status_code, 422)

    def test_member_preferences_accepts_partial_sms_patch(self):
        user_id = str(ObjectId())
        user_doc = {"_id": ObjectId(user_id), "isAdmin": False, "notifPrefs": ["email"], "phone": "+15550001111"}
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        expected = {"id": user_id, "emailNotifications": True, "smsNotifications": True, "hasPhone": True}
        with patch("controllers.auth_guard.find_user", return_value=user_doc), patch(
            "controllers.member_controller.update_member_notification_preferences", return_value=expected
        ) as prefs_mock:
            response = self.client.patch("/api/member/preferences", json={"smsNotifications": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, expected)
        self.assertEqual(prefs_mock.call_args.kwargs["sms_notifications"], True)

    def test_member_preferences_rejects_non_boolean_sms(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.patch("/api/member/preferences", json={"smsNotifications": "yes"})

        self.assertEqual(response.status_code, 422)

    def test_member_preferences_rejects_empty_patch(self):
        user_id = str(ObjectId())
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(user_id), "isAdmin": False}):
            response = self.client.patch("/api/member/preferences", json={})

        self.assertEqual(response.status_code, 400)

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
        channels = [object()]

        with patch("controllers.auth_guard.find_user", return_value={"_id": ObjectId(session_user_id), "isAdmin": True}), patch(
            "controllers.notifications_controller.build_notification_channels",
            return_value=channels,
        ) as channels_factory_mock, patch(
            "controllers.notifications_controller.WeeklySummaryNotifier",
            return_value=notifier,
        ) as notifier_ctor_mock:
            response = self.client.post(
                "/admin/notifications/summary",
                json={"userId": target_user_id, "weekStart": "2026-02-15", "weekEnd": "2026-02-21"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, notify_result)
        channels_factory_mock.assert_called_once_with(testing=True)
        self.assertEqual(notifier_ctor_mock.call_args.kwargs["channels"], channels)
        notifier.notifyWeeklySummary.assert_called_once_with(
            userId=ObjectId(target_user_id),
            weekStart=date(2026, 2, 15),
            weekEnd=date(2026, 2, 21),
            triggeredBy="admin",
        )

if __name__ == "__main__":
    unittest.main()
