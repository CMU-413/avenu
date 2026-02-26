import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import MailProviderError
from services.notifications.providers.factory import build_email_provider, build_sms_provider
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider
from services.notifications.providers.sms_provider import SMSProviderError
from services.notifications.providers.twilio_sms_provider import TwilioSMSProvider
from services.notifications.channels.factory import build_notification_channels
from services.notifications.providers.console_sms_provider import ConsoleSMSProvider


class ProviderFactoryTests(unittest.TestCase):
    def test_factory_returns_console_provider_in_testing_mode(self):
        provider = build_email_provider(testing=True)
        self.assertIsInstance(provider, ConsoleEmailProvider)

    def test_factory_returns_ms_graph_provider_when_required_env_present(self):
        with patch.dict(
            os.environ,
            {
                "MS_GRAPH_TENANT_ID": "tenant-id",
                "MS_GRAPH_CLIENT_ID": "client-id",
                "MS_GRAPH_CLIENT_SECRET": "client-secret",
                "MS_GRAPH_SENDER_EMAIL": "mail@avenu.example",
            },
            clear=False,
        ):
            provider = build_email_provider(testing=False)

        self.assertIsInstance(provider, MSGraphEmailProvider)

    def test_factory_raises_mail_provider_error_when_ms_graph_env_missing(self):
        with patch.dict(
            os.environ,
            {
                "MS_GRAPH_TENANT_ID": "",
                "MS_GRAPH_CLIENT_ID": "",
                "MS_GRAPH_CLIENT_SECRET": "",
                "MS_GRAPH_SENDER_EMAIL": "",
            },
            clear=False,
        ):
            with self.assertRaises(MailProviderError):
                build_email_provider(testing=False)

    def test_build_sms_provider_returns_twilio_provider_when_env_present(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "acct-id",
                "TWILIO_AUTH_TOKEN": "auth-token",
                "TWILIO_PHONE_NUMBER": "+15550001111",
            },
            clear=False,
        ):
            provider = build_sms_provider(testing=False)

        self.assertIsInstance(provider, TwilioSMSProvider)

    def test_build_sms_provider_raises_when_twilio_env_missing(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "",
                "TWILIO_AUTH_TOKEN": "",
                "TWILIO_PHONE_NUMBER": "",
            },
            clear=False,
        ):
            with self.assertRaises(SMSProviderError):
                build_sms_provider(testing=False)

    def test_build_sms_provider_returns_console_provider_in_testing_mode(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "",
                "TWILIO_AUTH_TOKEN": "",
                "TWILIO_PHONE_NUMBER": "",
            },
            clear=False,
        ):
            provider = build_sms_provider(testing=True)

        self.assertIsInstance(provider, ConsoleSMSProvider)

    def test_build_notification_channels_requires_twilio_when_not_testing(self):
        with patch.dict(
            os.environ,
            {
                "MS_GRAPH_TENANT_ID": "tenant-id",
                "MS_GRAPH_CLIENT_ID": "client-id",
                "MS_GRAPH_CLIENT_SECRET": "client-secret",
                "MS_GRAPH_SENDER_EMAIL": "mail@avenu.example",
                "TWILIO_ACCOUNT_SID": "",
                "TWILIO_AUTH_TOKEN": "",
                "TWILIO_PHONE_NUMBER": "",
            },
            clear=False,
        ):
            with self.assertRaises(SMSProviderError):
                build_notification_channels(testing=False)


if __name__ == "__main__":
    unittest.main()
