from __future__ import annotations

from typing import Callable, Protocol
from typing import cast

from twilio.rest import Client

from services.notifications.providers.sms_provider import SMSProvider, SMSProviderError, SMSProviderResult


class _TwilioMessageInstance(Protocol):
    sid: str | None


class _TwilioMessageCreator(Protocol):
    def create(self, *, body: str, from_: str, to: str) -> _TwilioMessageInstance:
        ...


class _TwilioClient(Protocol):
    @property
    def messages(self) -> _TwilioMessageCreator:
        ...


class TwilioSMSProvider(SMSProvider):
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_phone: str,
        client_factory: Callable[[str, str], _TwilioClient] | None = None,
    ) -> None:
        self._account_sid = self._require_value("TWILIO_ACCOUNT_SID", account_sid)
        self._auth_token = self._require_value("TWILIO_AUTH_TOKEN", auth_token)
        self._from_phone = self._require_value("TWILIO_PHONE_NUMBER", from_phone)
        factory = client_factory or cast(Callable[[str, str], _TwilioClient], Client)
        self._client = factory(self._account_sid, self._auth_token)

    def send(self, *, to: str, body: str) -> SMSProviderResult:
        try:
            message = self._client.messages.create(
                body=body,
                from_=self._from_phone,
                to=to,
            )
        except Exception as exc:
            raise SMSProviderError(f"Twilio request failed: {exc}") from exc

        sid = message.sid
        if sid is None or not sid.strip():
            raise SMSProviderError("Twilio send response missing sid")
        return {"messageId": sid}

    def _require_value(self, env_name: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise SMSProviderError(f"{env_name} is required")
        return normalized
