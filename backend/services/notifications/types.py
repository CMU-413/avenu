from __future__ import annotations

from typing import Any, Literal, TypedDict

ChannelStatus = Literal["sent", "failed"]
NotifyStatus = Literal["sent", "skipped", "failed"]
NotifyReason = Literal["opted_out", "empty_summary", "user_not_found", "all_channels_failed"]
NotifyTrigger = Literal["cron", "admin"]


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


class ChannelResult(TypedDict, total=False):
    channel: str
    status: ChannelStatus
    error: str


class NotifyResult(TypedDict, total=False):
    status: NotifyStatus
    channelResults: list[ChannelResult]
    reason: NotifyReason
