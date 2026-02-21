from __future__ import annotations

from services.notifications.channels.email_channel import EmailChannel
from services.notifications.channels.sms_channel import SMSChannel
from services.notifications.interfaces import NotificationChannel
from services.notifications.providers.factory import build_email_provider, build_sms_provider


def build_notification_channels(*, testing: bool, enable_sms_channel: bool) -> list[NotificationChannel]:
    channels: list[NotificationChannel] = [EmailChannel(build_email_provider(testing=testing))]
    if enable_sms_channel:
        channels.append(SMSChannel(build_sms_provider(testing=testing)))
    return channels
