from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from config import mail_requests_collection


def create_mail_request(doc: dict[str, Any]) -> dict[str, Any] | None:
    inserted = mail_requests_collection.insert_one(doc)
    return mail_requests_collection.find_one({"_id": inserted.inserted_id})


def find_mail_request(request_id: ObjectId) -> dict[str, Any] | None:
    return mail_requests_collection.find_one({"_id": request_id})


def list_mail_requests(query: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mail_requests_collection.find(query).sort([("createdAt", -1), ("_id", -1)]))


def cancel_member_active_request(*, request_id: ObjectId, member_id: ObjectId, now: datetime) -> int:
    result = mail_requests_collection.update_one(
        {"_id": request_id, "memberId": member_id, "status": "ACTIVE"},
        {"$set": {"status": "CANCELLED", "updatedAt": now}},
    )
    return result.matched_count


def resolve_active_request(*, request_id: ObjectId, admin_id: ObjectId, now: datetime) -> int:
    result = mail_requests_collection.update_one(
        {"_id": request_id, "status": "ACTIVE"},
        {
            "$set": {
                "status": "RESOLVED",
                "resolvedAt": now,
                "resolvedBy": admin_id,
                "updatedAt": now,
            }
        },
    )
    modified_count = getattr(result, "modified_count", None)
    if modified_count is None:
        modified_count = getattr(result, "matched_count", 0)
    return modified_count


def update_request_notification_status(
    *, request_id: ObjectId, status: str, notification_at: datetime
) -> None:
    mail_requests_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "lastNotificationStatus": status,
                "lastNotificationAt": notification_at,
                "updatedAt": notification_at,
            }
        },
    )
