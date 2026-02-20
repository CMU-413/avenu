from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from bson import ObjectId

from config import mail_requests_collection, notification_log_collection
from errors import APIError
from models import build_mail_request_create
from services.mailbox_access_service import assert_member_mailbox_access
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.log_repository import insert_special_case_notification_log
from services.notifications.providers.factory import build_email_provider
from services.notifications.special_case_notifier import SpecialCaseNotifier


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


def list_member_mail_requests(
    *,
    user: dict[str, Any],
    status_filter: Literal["ACTIVE", "RESOLVED", "ALL"] = "ACTIVE",
) -> list[dict[str, Any]]:
    if status_filter == "ALL":
        query: dict[str, Any] = {"memberId": user["_id"], "status": {"$in": ["ACTIVE", "RESOLVED"]}}
    else:
        query = {"memberId": user["_id"], "status": status_filter}
    return list(mail_requests_collection.find(query).sort([("createdAt", -1), ("_id", -1)]))


def list_member_active_mail_requests(*, user: dict[str, Any]) -> list[dict[str, Any]]:
    return list_member_mail_requests(user=user, status_filter="ACTIVE")


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


def _default_special_case_notifier() -> SpecialCaseNotifier:
    return SpecialCaseNotifier(channels=[EmailChannel(build_email_provider(testing=False))])


def _log_special_case_exception(*, user_id: ObjectId, exc: Exception) -> None:
    insert_special_case_notification_log(
        notification_log_collection,
        user_id=user_id,
        status="failed",
        reason="all_channels_failed",
        triggered_by="admin",
        error_message=str(exc),
        sent_at=None,
    )


def _notification_status_from_notify_result(result: dict[str, Any]) -> Literal["SENT", "FAILED"]:
    return "SENT" if result.get("status") == "sent" else "FAILED"


def resolve_mail_request_and_notify(
    *,
    request_id: ObjectId,
    admin_user: dict[str, Any],
    notifier: SpecialCaseNotifier | None = None,
) -> dict[str, Any]:
    admin_id = admin_user.get("_id") if isinstance(admin_user, dict) else None
    if not isinstance(admin_id, ObjectId):
        raise APIError(403, "forbidden")
    now = _utcnow()
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
    if modified_count != 1:
        raise APIError(404, "mail request not found")

    updated = mail_requests_collection.find_one({"_id": request_id})
    if not updated:
        raise APIError(500, "mail request missing after resolve")
    member_id = updated.get("memberId")
    if not isinstance(member_id, ObjectId):
        raise APIError(500, "mail request has invalid member id")

    resolved_notifier = notifier or _default_special_case_notifier()
    notification_status: Literal["SENT", "FAILED"] = "FAILED"
    notification_at = _utcnow()
    try:
        notify_result = resolved_notifier.notifySpecialCase(
            userId=member_id,
            triggeredBy="admin",
        )
        notification_status = _notification_status_from_notify_result(notify_result)
    except Exception as exc:
        _log_special_case_exception(user_id=member_id, exc=exc)
        notification_status = "FAILED"

    mail_requests_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "lastNotificationStatus": notification_status,
                "lastNotificationAt": notification_at,
                "updatedAt": notification_at,
            }
        },
    )

    refreshed = mail_requests_collection.find_one({"_id": request_id})
    if not refreshed:
        raise APIError(500, "mail request missing after notification")
    return refreshed


def retry_mail_request_notification(
    *,
    request_id: ObjectId,
    admin_user: dict[str, Any],
    notifier: SpecialCaseNotifier | None = None,
) -> dict[str, Any]:
    admin_id = admin_user.get("_id") if isinstance(admin_user, dict) else None
    if not isinstance(admin_id, ObjectId):
        raise APIError(403, "forbidden")
    request_doc = mail_requests_collection.find_one({"_id": request_id, "status": "RESOLVED"})
    if not request_doc:
        raise APIError(404, "mail request not found")

    member_id = request_doc.get("memberId")
    if not isinstance(member_id, ObjectId):
        raise APIError(500, "mail request has invalid member id")

    resolved_notifier = notifier or _default_special_case_notifier()
    notification_status: Literal["SENT", "FAILED"] = "FAILED"
    notification_at = _utcnow()
    try:
        notify_result = resolved_notifier.notifySpecialCase(
            userId=member_id,
            triggeredBy="admin",
        )
        notification_status = _notification_status_from_notify_result(notify_result)
    except Exception as exc:
        _log_special_case_exception(user_id=member_id, exc=exc)
        notification_status = "FAILED"

    mail_requests_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "lastNotificationStatus": notification_status,
                "lastNotificationAt": notification_at,
                "updatedAt": notification_at,
            }
        },
    )
    refreshed = mail_requests_collection.find_one({"_id": request_id})
    if not refreshed:
        raise APIError(500, "mail request missing after notification retry")
    return refreshed
