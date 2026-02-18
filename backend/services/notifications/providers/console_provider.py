from __future__ import annotations

from services.notifications.providers.email_provider import EmailProvider


class ConsoleEmailProvider(EmailProvider):
    def send(self, *, to: str, subject: str, html: str) -> str:
        print("=== EMAIL SEND ===")
        print("To:", to)
        print("Subject:", subject)
        print("HTML:", html[:200], "...")
        print("==================")
        return "console-message-id"
