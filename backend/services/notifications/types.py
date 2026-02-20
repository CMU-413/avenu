from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, TypedDict

from bson import ObjectId

ChannelStatus = Literal["sent", "failed"]
NotifyStatus = Literal["sent", "skipped", "failed"]
NotifyReason = Literal["already_sent", "opted_out", "empty_summary", "user_not_found", "all_channels_failed"]
NotifyTrigger = Literal["cron", "admin"]
NotificationType = Literal["weekly-summary", "special-case"]
NotificationLogStatus = Literal["sent", "skipped", "failed"]


class WeeklySummaryUser(TypedDict):
    id: str
    email: str
    fullname: str


class WeeklySummaryData(TypedDict):
    weekStart: str
    weekEnd: str
    totalLetters: int
    totalPackages: int
    mailboxes: list[dict[str, Any]]


class WeeklySummaryNotificationPayload(TypedDict):
    user: WeeklySummaryUser
    triggeredBy: NotifyTrigger
    summary: WeeklySummaryData


class SpecialCaseMailRequestContext(TypedDict, total=False):
    requestId: str
    mailboxId: str
    expectedSender: str | None
    description: str | None
    startDate: str | None
    endDate: str | None
    resolvedAt: str | None


class SpecialCaseNotificationPayload(TypedDict):
    user: WeeklySummaryUser
    triggeredBy: NotifyTrigger
    templateType: Literal["mail-arrived"]
    mailRequest: SpecialCaseMailRequestContext | None


class ChannelResult(TypedDict, total=False):
    channel: str
    status: ChannelStatus
    messageId: str
    error: str


class NotifyResult(TypedDict, total=False):
    status: NotifyStatus
    channelResults: list[ChannelResult]
    reason: NotifyReason


class NotificationLogEntry(TypedDict):
    userId: ObjectId
    type: NotificationType
    weekStart: datetime | None
    templateType: Literal["mail-arrived"] | None
    mailboxId: ObjectId | None
    status: NotificationLogStatus
    reason: NotifyReason | None
    triggeredBy: NotifyTrigger
    errorMessage: str | None
    sentAt: datetime | None


class WeeklyCronJobResult(TypedDict):
    weekStart: date
    weekEnd: date
    processed: int
    sent: int
    skipped: int
    failed: int
    errors: int
