from __future__ import annotations

from typing import TypedDict


class UserEntity(TypedDict, total=False):
    id: str
    optixId: int
    isAdmin: bool
    fullname: str
    email: str
    phone: str | None


class TeamEntity(TypedDict, total=False):
    id: str
    optixId: int
    name: str


class MailboxEntity(TypedDict, total=False):
    id: str
    type: str
    refId: str
    displayName: str


class MailEntryEntity(TypedDict, total=False):
    id: str
    mailboxId: str
    date: str
    type: str
    receiverName: str | None
    senderInfo: str | None


class WeeklySummaryEntity(TypedDict, total=False):
    weekStart: str
    weekEnd: str
    totalLetters: int
    totalPackages: int


class NotificationLogEntity(TypedDict, total=False):
    id: str
    userId: str
    type: str
    status: str
    reason: str | None
