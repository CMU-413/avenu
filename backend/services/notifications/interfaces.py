from __future__ import annotations

from datetime import date
from typing import Protocol

from bson import ObjectId

from services.notifications.types import (
    ChannelResult,
    NotifyResult,
    NotifyTrigger,
    SpecialCaseNotificationPayload,
    WeeklySummaryNotificationPayload,
)


class NotificationChannel(Protocol):
    channel: str

    def send(self, payload: WeeklySummaryNotificationPayload | SpecialCaseNotificationPayload) -> ChannelResult:
        ...


class Notifier(Protocol):
    def notifyWeeklySummary(
        self,
        *,
        userId: ObjectId,
        weekStart: date,
        weekEnd: date,
        triggeredBy: NotifyTrigger,
    ) -> NotifyResult:
        ...

    def notifySpecialCase(
        self,
        *,
        userId: ObjectId,
        triggeredBy: NotifyTrigger,
    ) -> NotifyResult:
        ...
