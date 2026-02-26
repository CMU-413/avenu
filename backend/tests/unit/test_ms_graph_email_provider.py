import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.providers.email_provider import MailProviderError
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider


class _FakeHTTPResponse:
    def __init__(self, *, status_code: int, body: str):
        self._status_code = status_code
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def getcode(self):
        return self._status_code

    def read(self):
        return self._body.encode("utf-8")


class MSGraphEmailProviderTests(unittest.TestCase):
    def _build_provider(self) -> MSGraphEmailProvider:
        return MSGraphEmailProvider(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="client-secret",
            sender_email="mail@avenu.example",
        )

    def test_send_uses_cached_token_until_expiry(self):
        provider = self._build_provider()
        seen_urls = []

        responses = iter(
            [
                _FakeHTTPResponse(status_code=200, body=json.dumps({"access_token": "token-1", "expires_in": 3600})),
                _FakeHTTPResponse(status_code=202, body=""),
                _FakeHTTPResponse(status_code=202, body=""),
            ]
        )

        def fake_urlopen(request, timeout):
            _ = timeout
            seen_urls.append(request.full_url)
            return next(responses)

        with patch("services.notifications.providers.ms_graph_provider.urlopen", side_effect=fake_urlopen):
            first = provider.send(to="first@example.com", subject="One", html="<p>One</p>")
            second = provider.send(to="second@example.com", subject="Two", html="<p>Two</p>")

        self.assertEqual(first, "msgraph-accepted")
        self.assertEqual(second, "msgraph-accepted")
        self.assertEqual(
            seen_urls,
            [
                "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/token",
                "https://graph.microsoft.com/v1.0/users/mail@avenu.example/sendMail",
                "https://graph.microsoft.com/v1.0/users/mail@avenu.example/sendMail",
            ],
        )

    def test_send_refreshes_token_after_expiry(self):
        provider = self._build_provider()
        token_urls = []

        responses = iter(
            [
                _FakeHTTPResponse(status_code=200, body=json.dumps({"access_token": "token-1", "expires_in": 3600})),
                _FakeHTTPResponse(status_code=202, body=""),
                _FakeHTTPResponse(status_code=200, body=json.dumps({"access_token": "token-2", "expires_in": 3600})),
                _FakeHTTPResponse(status_code=202, body=""),
            ]
        )

        def fake_urlopen(request, timeout):
            _ = timeout
            if request.full_url.endswith("/token"):
                token_urls.append(request.full_url)
            return next(responses)

        with patch("services.notifications.providers.ms_graph_provider.urlopen", side_effect=fake_urlopen):
            provider.send(to="member@example.com", subject="A", html="<p>A</p>")
            provider._access_token_expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
            provider.send(to="member@example.com", subject="B", html="<p>B</p>")

        self.assertEqual(len(token_urls), 2)

    def test_send_raises_mail_provider_error_when_token_request_fails(self):
        provider = self._build_provider()

        with patch(
            "services.notifications.providers.ms_graph_provider.urlopen",
            return_value=_FakeHTTPResponse(status_code=401, body="invalid_client"),
        ):
            with self.assertRaises(MailProviderError):
                provider.send(to="member@example.com", subject="Subject", html="<p>Hello</p>")

    def test_send_raises_mail_provider_error_when_sendmail_not_202(self):
        provider = self._build_provider()
        responses = iter(
            [
                _FakeHTTPResponse(status_code=200, body=json.dumps({"access_token": "token-1", "expires_in": 3600})),
                _FakeHTTPResponse(status_code=500, body="mailbox unavailable"),
            ]
        )

        with patch(
            "services.notifications.providers.ms_graph_provider.urlopen",
            side_effect=lambda request, timeout: next(responses),
        ):
            with self.assertRaises(MailProviderError):
                provider.send(to="member@example.com", subject="Subject", html="<p>Hello</p>")

    def test_send_returns_stable_message_id_on_202(self):
        provider = self._build_provider()
        responses = iter(
            [
                _FakeHTTPResponse(status_code=200, body=json.dumps({"access_token": "token-1", "expires_in": 3600})),
                _FakeHTTPResponse(status_code=202, body=""),
            ]
        )

        with patch(
            "services.notifications.providers.ms_graph_provider.urlopen",
            side_effect=lambda request, timeout: next(responses),
        ):
            message_id = provider.send(to="member@example.com", subject="Subject", html="<p>Hello</p>")

        self.assertEqual(message_id, "msgraph-accepted")


if __name__ == "__main__":
    unittest.main()
