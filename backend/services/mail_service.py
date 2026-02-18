from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from config import mail_collection, mailboxes_collection
from errors import APIError
from models import build_mail_create, build_mail_patch


def _ensure_mailbox_exists(mailbox_id: ObjectId) -> None:
    exists = mailboxes_collection.find_one({"_id": mailbox_id}, {"_id": 1})
    if not exists:
        raise APIError(422, "mailbox does not exist")


def list_mail(
    *,
    day_start: datetime | None = None,
    day_end: datetime | None = None,
    mailbox_id: ObjectId | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if day_start is not None and day_end is not None:
        query["date"] = {"$gte": day_start, "$lt": day_end}
    if mailbox_id is not None:
        query["mailboxId"] = mailbox_id
    return list(mail_collection.find(query).sort([("mailboxId", 1), ("date", 1), ("type", 1)]))


def get_mail(mail_id: ObjectId) -> dict[str, Any] | None:
    return mail_collection.find_one({"_id": mail_id})


def create_mail(payload: dict[str, Any]) -> dict[str, Any]:
    doc = build_mail_create(payload)
    _ensure_mailbox_exists(doc["mailboxId"])
    inserted = mail_collection.insert_one(doc)
    created = mail_collection.find_one({"_id": inserted.inserted_id})
    if not created:
        raise APIError(500, "failed to create mail")
    return created


def update_mail(mail_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_mail_patch(payload)
    if "mailboxId" in patch:
        _ensure_mailbox_exists(patch["mailboxId"])

    result = mail_collection.update_one({"_id": mail_id}, {"$set": patch})
    if result.matched_count == 0:
        raise APIError(404, "mail not found")
    updated = mail_collection.find_one({"_id": mail_id})
    if not updated:
        raise APIError(500, "failed to fetch updated mail")
    return updated


def delete_mail(mail_id: ObjectId) -> None:
    mail_collection.delete_one({"_id": mail_id})
