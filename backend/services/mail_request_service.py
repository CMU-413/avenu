from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from config import mail_requests_collection
from errors import APIError
from models import build_mail_request_create
from services.mailbox_access_service import assert_member_mailbox_access


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_mail_request(*, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    doc = build_mail_request_create(payload, member_id=user["_id"])
    assert_member_mailbox_access(user, doc["mailboxId"])
    inserted = mail_requests_collection.insert_one(doc)
    created = mail_requests_collection.find_one({"_id": inserted.inserted_id})
    if not created:
        raise APIError(500, "failed to create mail request")
    return created


def list_member_active_mail_requests(*, user: dict[str, Any]) -> list[dict[str, Any]]:
    query = {"memberId": user["_id"], "status": "ACTIVE"}
    return list(mail_requests_collection.find(query).sort([("createdAt", -1), ("_id", -1)]))


def cancel_member_mail_request(*, user: dict[str, Any], request_id: ObjectId) -> None:
    result = mail_requests_collection.update_one(
        {
            "_id": request_id,
            "memberId": user["_id"],
            "status": "ACTIVE",
        },
        {"$set": {"status": "CANCELLED", "updatedAt": _utcnow()}},
    )
    if result.matched_count == 0:
        raise APIError(404, "mail request not found")


def list_admin_active_mail_requests(
    *,
    mailbox_id: ObjectId | None = None,
    member_id: ObjectId | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"status": "ACTIVE"}
    if mailbox_id is not None:
        query["mailboxId"] = mailbox_id
    if member_id is not None:
        query["memberId"] = member_id
    return list(mail_requests_collection.find(query).sort([("createdAt", -1), ("_id", -1)]))
