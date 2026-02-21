import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.providers.sms_provider import SMSProviderError
from services.notifications.providers.twilio_sms_provider import TwilioSMSProvider


class TwilioSMSProviderTests(unittest.TestCase):
    def test_send_posts_twilio_message_and_returns_sid(self):
        provider = TwilioSMSProvider(
            account_sid="acct-123",
            auth_token="token-123",
            from_phone="+15550001111",
            api_base_url="https://api.twilio.test",
        )
        response = Mock()
        response.ok = True
        response.status_code = 201
        response.text = '{"sid":"SM123"}'
        response.json.return_value = {"sid": "SM123"}

        with patch("services.notifications.providers.twilio_sms_provider.requests.post", return_value=response) as post_mock:
            result = provider.send(to="+15550002222", body="test body")

        self.assertEqual(result, {"messageId": "SM123"})
        post_mock.assert_called_once_with(
            "https://api.twilio.test/2010-04-01/Accounts/acct-123/Messages.json",
            auth=("acct-123", "token-123"),
            data={"From": "+15550001111", "To": "+15550002222", "Body": "test body"},
            timeout=10.0,
        )

    def test_send_raises_sms_provider_error_on_http_error(self):
        provider = TwilioSMSProvider(
            account_sid="acct-123",
            auth_token="token-123",
            from_phone="+15550001111",
        )
        response = Mock()
        response.ok = False
        response.status_code = 400
        response.text = "bad request"

        with patch("services.notifications.providers.twilio_sms_provider.requests.post", return_value=response):
            with self.assertRaises(SMSProviderError) as ctx:
                provider.send(to="+15550002222", body="test body")

        self.assertIn("status=400", str(ctx.exception))

    def test_send_raises_sms_provider_error_when_sid_missing(self):
        provider = TwilioSMSProvider(
            account_sid="acct-123",
            auth_token="token-123",
            from_phone="+15550001111",
        )
        response = Mock()
        response.ok = True
        response.status_code = 201
        response.text = "{}"
        response.json.return_value = {}

        with patch("services.notifications.providers.twilio_sms_provider.requests.post", return_value=response):
            with self.assertRaises(SMSProviderError) as ctx:
                provider.send(to="+15550002222", body="test body")

        self.assertIn("missing sid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
