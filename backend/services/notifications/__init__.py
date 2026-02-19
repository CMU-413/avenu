from services.notifications.channels.email_channel import EmailChannel
from services.notifications.interfaces import NotificationChannel, Notifier
from services.notifications.log_repository import (
    MAIL_ARRIVED_TEMPLATE_TYPE,
    SPECIAL_CASE_TYPE,
    WEEKLY_SUMMARY_TYPE,
    find_sent_weekly_summary,
    insert_notification_log,
    insert_special_case_notification_log,
)
from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.providers.email_provider import EmailProvider, MailProviderError
from services.notifications.providers.factory import build_email_provider
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider
from services.notifications.special_case_notifier import SpecialCaseNotifier
from services.notifications.types import (
    ChannelResult,
    NotificationLogEntry,
    NotificationLogStatus,
    NotificationType,
    NotifyReason,
    NotifyResult,
    NotifyStatus,
    NotifyTrigger,
    SpecialCaseNotificationPayload,
    WeeklyCronJobResult,
    WeeklySummaryNotificationPayload,
)
from services.notifications.weekly_summary_cron_job import compute_previous_week_range, run_weekly_summary_cron_job
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier

__all__ = [
    "ChannelResult",
    "build_email_provider",
    "ConsoleEmailProvider",
    "EmailChannel",
    "EmailProvider",
    "MailProviderError",
    "MSGraphEmailProvider",
    "NotificationChannel",
    "NotificationLogEntry",
    "NotificationLogStatus",
    "NotificationType",
    "Notifier",
    "NotifyReason",
    "NotifyResult",
    "NotifyStatus",
    "NotifyTrigger",
    "SpecialCaseNotificationPayload",
    "SpecialCaseNotifier",
    "WeeklyCronJobResult",
    "WEEKLY_SUMMARY_TYPE",
    "SPECIAL_CASE_TYPE",
    "MAIL_ARRIVED_TEMPLATE_TYPE",
    "WeeklySummaryNotificationPayload",
    "WeeklySummaryNotifier",
    "compute_previous_week_range",
    "find_sent_weekly_summary",
    "insert_notification_log",
    "insert_special_case_notification_log",
    "run_weekly_summary_cron_job",
]
