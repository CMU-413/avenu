from __future__ import annotations

from typing import Any

from bson import ObjectId

from config import mailboxes_collection
from errors import APIError
from models import build_mailbox_patch


def list_mailboxes() -> list[dict[str, Any]]:
    return list(mailboxes_collection.find())


def get_mailbox(mailbox_id: ObjectId) -> dict[str, Any] | None:
    return mailboxes_collection.find_one({"_id": mailbox_id})


def update_mailbox(mailbox_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_mailbox_patch(payload)
    result = mailboxes_collection.update_one({"_id": mailbox_id}, {"$set": patch})
    if result.matched_count == 0:
        raise APIError(404, "mailbox not found")
    updated = mailboxes_collection.find_one({"_id": mailbox_id})
    if not updated:
        raise APIError(500, "failed to fetch updated mailbox")
    return updated
