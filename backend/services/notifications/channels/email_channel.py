from __future__ import annotations

from datetime import date, datetime
from typing import Union

from flask import render_template

from services.notifications.providers.email_provider import EmailProvider
from services.notifications.types import ChannelResult, WeeklySummaryData, WeeklySummaryNotificationPayload


class EmailChannel:
    channel = "email"

    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def send(self, payload: WeeklySummaryNotificationPayload) -> ChannelResult:
        html = render_template(
            "emails/weekly_summary.html",
            summary=payload["summary"],
            user=payload["user"],
        )

        subject = self._build_subject(payload["summary"])

        try:
            message_id = self.provider.send(
                to=payload["user"]["email"],
                subject=subject,
                html=html,
            )
            return {
                "channel": self.channel,
                "status": "sent",
                "messageId": message_id,
            }
        except Exception as exc:
            return {
                "channel": self.channel,
                "status": "failed",
                "error": str(exc),
            }

    def _build_subject(self, summary: WeeklySummaryData) -> str:
        week_start = self._format_summary_date(summary["weekStart"])
        week_end = self._format_summary_date(summary["weekEnd"])
        return f"Your Avenu Mail Summary ({week_start}–{week_end})"

    def _format_summary_date(self, value: Union[str, date, datetime]) -> str:
        if isinstance(value, datetime):
            return value.strftime("%b %d")
        if isinstance(value, date):
            return value.strftime("%b %d")
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d")
