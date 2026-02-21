from services.notifications.channels.email_channel import EmailChannel
from services.notifications.channels.factory import build_notification_channels
from services.notifications.channels.sms_channel import SMSChannel
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
from services.notifications.providers.factory import build_email_provider, build_sms_provider
from services.notifications.providers.ms_graph_provider import MSGraphEmailProvider
from services.notifications.providers.sms_provider import SMSProvider, SMSProviderError, SMSProviderResult
from services.notifications.providers.twilio_sms_provider import TwilioSMSProvider
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
    "build_sms_provider",
    "build_notification_channels",
    "ConsoleEmailProvider",
    "EmailChannel",
    "SMSChannel",
    "EmailProvider",
    "MailProviderError",
    "MSGraphEmailProvider",
    "SMSProvider",
    "SMSProviderError",
    "SMSProviderResult",
    "TwilioSMSProvider",
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
