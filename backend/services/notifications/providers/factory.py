from __future__ import annotations

import os

from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import EmailProvider, MailProviderError
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider
from services.notifications.providers.sms_provider import SMSProvider, SMSProviderError
from services.notifications.providers.twilio_sms_provider import TwilioSMSProvider


def build_email_provider(*, testing: bool) -> EmailProvider:
    if testing:
        return ConsoleEmailProvider()
    return MSGraphEmailProvider(
        tenant_id=_required_env("MS_GRAPH_TENANT_ID"),
        client_id=_required_env("MS_GRAPH_CLIENT_ID"),
        client_secret=_required_env("MS_GRAPH_CLIENT_SECRET"),
        sender_email=_required_env("MS_GRAPH_SENDER_EMAIL"),
    )


def build_sms_provider(*, testing: bool) -> SMSProvider:
    _ = testing
    return TwilioSMSProvider(
        account_sid=_required_env("TWILIO_ACCOUNT_SID", exc_type=SMSProviderError),
        auth_token=_required_env("TWILIO_AUTH_TOKEN", exc_type=SMSProviderError),
        from_phone=_required_env("TWILIO_PHONE_NUMBER", exc_type=SMSProviderError),
    )


def _required_env(name: str, *, exc_type: type[RuntimeError] = MailProviderError) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise exc_type(f"{name} is required")
    return value
