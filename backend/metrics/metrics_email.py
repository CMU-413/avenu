from __future__ import annotations

from prometheus_client import Counter, Histogram

emails_sent_total = Counter(
    "emails_sent_total",
    "Email notifications successfully sent via the provider",
)

emails_failed_total = Counter(
    "emails_failed_total",
    "Email notification attempts that failed in the channel",
)

email_send_duration_seconds = Histogram(
    "email_send_duration_seconds",
    "Duration of the email provider send call in seconds",
)
