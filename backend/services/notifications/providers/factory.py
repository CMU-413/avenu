from __future__ import annotations

import os

from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import EmailProvider, MailProviderError
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider


def build_email_provider(*, testing: bool) -> EmailProvider:
    if testing:
        return ConsoleEmailProvider()
    return MSGraphEmailProvider(
        tenant_id=_required_env("MS_GRAPH_TENANT_ID"),
        client_id=_required_env("MS_GRAPH_CLIENT_ID"),
        client_secret=_required_env("MS_GRAPH_CLIENT_SECRET"),
        sender_email=_required_env("MS_GRAPH_SENDER_EMAIL"),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise MailProviderError(f"{name} is required")
    return value
