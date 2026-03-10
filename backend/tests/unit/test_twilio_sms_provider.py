import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.providers.sms_provider import SMSProviderError
from services.notifications.providers.twilio_sms_provider import TwilioSMSProvider


class TwilioSMSProviderTests(unittest.TestCase):
    def test_send_uses_twilio_client_and_returns_sid(self):
        message = Mock()
        message.sid = "SM123"
        twilio_client = Mock()
        twilio_client.messages.create.return_value = message

        with patch("services.notifications.providers.twilio_sms_provider.Client", return_value=twilio_client) as client_cls:
            provider = TwilioSMSProvider(
                account_sid="acct-123",
                auth_token="token-123",
                from_phone="+15550001111",
            )
            result = provider.send(to="+15550002222", body="test body")

        self.assertEqual(result, {"messageId": "SM123"})
        client_cls.assert_called_once_with("acct-123", "token-123")
        twilio_client.messages.create.assert_called_once_with(
            body="test body",
            from_="+15550001111",
            to="+15550002222",
        )

    def test_send_raises_sms_provider_error_on_twilio_exception(self):
        twilio_client = Mock()
        twilio_client.messages.create.side_effect = RuntimeError("boom")
        with patch("services.notifications.providers.twilio_sms_provider.Client", return_value=twilio_client):
            provider = TwilioSMSProvider(
                account_sid="acct-123",
                auth_token="token-123",
                from_phone="+15550001111",
            )
            with self.assertRaises(SMSProviderError) as ctx:
                provider.send(to="+15550002222", body="test body")

        self.assertIn("Twilio request failed", str(ctx.exception))

    def test_send_raises_sms_provider_error_when_sid_missing(self):
        message = Mock()
        message.sid = ""
        twilio_client = Mock()
        twilio_client.messages.create.return_value = message
        with patch("services.notifications.providers.twilio_sms_provider.Client", return_value=twilio_client):
            provider = TwilioSMSProvider(
                account_sid="acct-123",
                auth_token="token-123",
                from_phone="+15550001111",
            )
            with self.assertRaises(SMSProviderError) as ctx:
                provider.send(to="+15550002222", body="test body")

        self.assertIn("missing sid", str(ctx.exception))

    def test_check_health_returns_healthy_when_account_fetch_succeeds(self):
        account = Mock()
        account.sid = "AC123"
        twilio_client = Mock()
        twilio_client.api.accounts.return_value.fetch.return_value = account

        with patch("services.notifications.providers.twilio_sms_provider.Client", return_value=twilio_client):
            provider = TwilioSMSProvider(
                account_sid="acct-123",
                auth_token="token-123",
                from_phone="+15550001111",
            )
            status = provider.check_health(timeout_seconds=0.2)

        self.assertEqual(status, "healthy")
        twilio_client.api.accounts.assert_called_once_with("acct-123")

    def test_check_health_returns_misconfigured_on_auth_error(self):
        twilio_client = Mock()
        twilio_client.api.accounts.return_value.fetch.side_effect = RuntimeError("authenticate")

        with patch("services.notifications.providers.twilio_sms_provider.Client", return_value=twilio_client):
            provider = TwilioSMSProvider(
                account_sid="acct-123",
                auth_token="token-123",
                from_phone="+15550001111",
            )
            status = provider.check_health(timeout_seconds=0.2)

        self.assertEqual(status, "misconfigured")


if __name__ == "__main__":
    unittest.main()
