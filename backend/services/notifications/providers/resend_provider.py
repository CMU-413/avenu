from __future__ import annotations

import resend

from services.notifications.providers.email_provider import EmailProvider


class ResendProvider(EmailProvider):
    def __init__(self, api_key: str, email_from: str):
        resend.api_key = api_key
        self.email_from = email_from

    def send(self, *, to: str, subject: str, html: str) -> str:
        response = resend.Emails.send(
            {
                "from": self.email_from,
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        return response["id"]
