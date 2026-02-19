import os
import unittest
from unittest.mock import patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import MailProviderError
from services.notifications.providers.factory import build_email_provider
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider


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


if __name__ == "__main__":
    unittest.main()
