from __future__ import annotations

from typing import Any

import requests

from services.notifications.providers.sms_provider import SMSProvider, SMSProviderError, SMSProviderResult


class TwilioSMSProvider(SMSProvider):
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_phone: str,
        timeout_seconds: float = 10.0,
        api_base_url: str = "https://api.twilio.com",
    ) -> None:
        self._account_sid = self._require_value("TWILIO_ACCOUNT_SID", account_sid)
        self._auth_token = self._require_value("TWILIO_AUTH_TOKEN", auth_token)
        self._from_phone = self._require_value("TWILIO_PHONE_NUMBER", from_phone)
        self._timeout_seconds = timeout_seconds
        self._api_base_url = api_base_url.rstrip("/")

    def send(self, *, to: str, body: str) -> SMSProviderResult:
        url = f"{self._api_base_url}/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        try:
            response = requests.post(
                url,
                auth=(self._account_sid, self._auth_token),
                data={"From": self._from_phone, "To": to, "Body": body},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SMSProviderError(f"Twilio request failed: {exc}") from exc

        if not response.ok:
            raise SMSProviderError(f"Twilio send failed status={response.status_code} body={response.text[:300]}")

        payload = self._parse_response_json(response)
        sid = payload.get("sid")
        if not isinstance(sid, str) or not sid:
            raise SMSProviderError("Twilio send response missing sid")
        return {"messageId": sid}

    def _parse_response_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            parsed = response.json()
        except ValueError as exc:
            raise SMSProviderError("Twilio send response is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise SMSProviderError("Twilio send response JSON must be an object")
        return parsed

    def _require_value(self, env_name: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise SMSProviderError(f"{env_name} is required")
        return normalized
