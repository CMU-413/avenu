from __future__ import annotations

import time
from datetime import date, datetime
from typing import Union

from flask import render_template

from metrics.metrics_email import email_send_duration_seconds, emails_failed_total, emails_sent_total
from services.notifications.providers.email_provider import EmailProvider
from services.notifications.types import (
    ChannelResult,
    SpecialCaseNotificationPayload,
    WeeklySummaryData,
    WeeklySummaryNotificationPayload,
)

MAIL_ARRIVED_TEMPLATE = {
    "subject": "Mail has arrived",
    "template": "emails/special_mail_arrived.html",
    "requires_mailbox": False,
}


class EmailChannel:
    channel = "email"

    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def send(self, payload: WeeklySummaryNotificationPayload | SpecialCaseNotificationPayload) -> ChannelResult:
        if "summary" in payload:
            html = render_template(
                "emails/weekly_summary.html",
                summary=payload["summary"],
                user=payload["user"],
            )
            subject = self._build_subject(payload["summary"])
        else:
            mail_request = payload.get("mailRequest")
            html = render_template(
                MAIL_ARRIVED_TEMPLATE["template"],
                user=payload["user"],
                mail_request=mail_request,
            )
            subject = MAIL_ARRIVED_TEMPLATE["subject"]
            if isinstance(mail_request, dict):
                expected_sender = mail_request.get("expectedSender")
                if isinstance(expected_sender, str) and expected_sender.strip():
                    subject = f"Mail has arrived: {expected_sender.strip()}"

        start = time.perf_counter()
        try:
            message_id = self.provider.send(
                to=payload["user"]["email"],
                subject=subject,
                html=html,
            )
            email_send_duration_seconds.observe(time.perf_counter() - start)
            emails_sent_total.inc()
            return {
                "channel": self.channel,
                "status": "sent",
                "messageId": message_id,
            }
        except Exception as exc:
            email_send_duration_seconds.observe(time.perf_counter() - start)
            emails_failed_total.inc()
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
