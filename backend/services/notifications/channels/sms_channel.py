from __future__ import annotations

from datetime import date, datetime
from typing import Union

from services.notifications.providers.sms_provider import SMSProvider
from validators import is_e164_phone
from services.notifications.types import ChannelResult, SpecialCaseNotificationPayload, WeeklySummaryData, WeeklySummaryNotificationPayload


class SMSChannel:
    channel = "sms"

    def __init__(self, provider: SMSProvider) -> None:
        self.provider = provider

    def send(self, payload: WeeklySummaryNotificationPayload | SpecialCaseNotificationPayload) -> ChannelResult:
        raw_phone = payload["user"].get("phone")
        if not isinstance(raw_phone, str) or not raw_phone.strip():
            return {"channel": self.channel, "status": "skipped", "error": "missing phone"}
        phone = raw_phone.strip()
        if not is_e164_phone(phone):
            return {"channel": self.channel, "status": "skipped", "error": "invalid phone for SMS"}

        if "summary" in payload:
            body = self._build_weekly_summary_body(payload)
        else:
            body = self._build_special_case_body(payload)

        try:
            result = self.provider.send(to=phone, body=body)
            return {
                "channel": self.channel,
                "status": "sent",
                "messageId": result["messageId"],
            }
        except Exception as exc:
            return {
                "channel": self.channel,
                "status": "failed",
                "error": str(exc),
            }

    def _build_weekly_summary_body(self, payload: WeeklySummaryNotificationPayload) -> str:
        summary = payload["summary"]
        week_start = self._format_summary_date(summary["weekStart"])
        week_end = self._format_summary_date(summary["weekEnd"])
        return (
            f"Avenu: Your weekly mail summary ({week_start}-{week_end}) is ready. "
            f"Letters: {summary['totalLetters']}, Packages: {summary['totalPackages']}."
        )

    def _build_special_case_body(self, payload: SpecialCaseNotificationPayload) -> str:
        mail_request = payload.get("mailRequest")
        if not isinstance(mail_request, dict):
            return "Avenu: Mail has arrived for you."

        expected_sender = mail_request.get("expectedSender")
        if isinstance(expected_sender, str) and expected_sender.strip():
            return f"Avenu: Mail has arrived from {expected_sender.strip()}."
        return "Avenu: Mail has arrived for one of your expected mail requests."

    def _format_summary_date(self, value: Union[str, date, datetime]) -> str:
        if isinstance(value, datetime):
            return value.strftime("%b %d")
        if isinstance(value, date):
            return value.strftime("%b %d")
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d")
