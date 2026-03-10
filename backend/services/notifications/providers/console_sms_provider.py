from __future__ import annotations

from services.notifications.providers.sms_provider import SMSProvider, SMSProviderResult


class ConsoleSMSProvider(SMSProvider):
    def send(self, *, to: str, body: str) -> SMSProviderResult:
        print("=== SMS SEND ===")
        print(f"To: {to}")
        print(f"Body: {body}")
        print("=== END SMS ===")
        return {"messageId": "console-sms-message-id"}

    def check_health(self, *, timeout_seconds: float) -> str:
        _ = timeout_seconds
        return "healthy"
