from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from bson import ObjectId

from errors import APIError
from models import build_mail_request_create
from repositories.mail_requests_repository import (
    cancel_member_active_request,
    create_mail_request as repo_create_mail_request,
    find_mail_request,
    list_mail_requests,
    resolve_active_request,
    update_request_notification_status,
)
from repositories.notification_logs_repository import insert_special_case_log
from services.mailbox_access_service import assert_member_mailbox_access
from services.notifications.channels.factory import build_notification_channels
from services.notifications.special_case_notifier import SpecialCaseNotifier


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_mail_request(*, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    doc = build_mail_request_create(payload, member_id=user["_id"])
    assert_member_mailbox_access(user, doc["mailboxId"])
    created = repo_create_mail_request(doc)
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
    return list_mail_requests(query)


def list_member_active_mail_requests(*, user: dict[str, Any]) -> list[dict[str, Any]]:
    return list_member_mail_requests(user=user, status_filter="ACTIVE")


def cancel_member_mail_request(*, user: dict[str, Any], request_id: ObjectId) -> None:
    if cancel_member_active_request(request_id=request_id, member_id=user["_id"], now=_utcnow()) == 0:
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
    return list_mail_requests(query)


def _default_special_case_notifier() -> SpecialCaseNotifier:
    return SpecialCaseNotifier(channels=build_notification_channels(testing=False))


def _log_special_case_exception(*, user_id: ObjectId, exc: Exception) -> None:
    insert_special_case_log(
        user_id=user_id,
        status="failed",
        reason="all_channels_failed",
        triggered_by="admin",
        error_message=str(exc),
        sent_at=None,
    )


def _notification_status_from_notify_result(result: dict[str, Any]) -> Literal["SENT", "SKIPPED", "FAILED"]:
    status = result.get("status")
    if status == "sent":
        return "SENT"
    if status == "skipped":
        return "SKIPPED"
    return "FAILED"


def _build_mail_request_notification_context(request_doc: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        "expectedSender": request_doc.get("expectedSender"),
        "description": request_doc.get("description"),
        "startDate": request_doc.get("startDate"),
        "endDate": request_doc.get("endDate"),
    }
    request_id = request_doc.get("_id")
    if request_id is not None:
        context["requestId"] = str(request_id)
    mailbox_id = request_doc.get("mailboxId")
    if mailbox_id is not None:
        context["mailboxId"] = str(mailbox_id)
    resolved_at = request_doc.get("resolvedAt")
    if isinstance(resolved_at, datetime):
        context["resolvedAt"] = resolved_at.isoformat()
    return context


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
    if resolve_active_request(request_id=request_id, admin_id=admin_id, now=now) != 1:
        raise APIError(404, "mail request not found")

    updated = find_mail_request(request_id)
    if not updated:
        raise APIError(500, "mail request missing after resolve")
    member_id = updated.get("memberId")
    if not isinstance(member_id, ObjectId):
        raise APIError(500, "mail request has invalid member id")

    resolved_notifier = notifier or _default_special_case_notifier()
    notification_status: Literal["SENT", "SKIPPED", "FAILED"] = "FAILED"
    notification_at = _utcnow()
    try:
        notify_result = resolved_notifier.notifySpecialCase(
            userId=member_id,
            triggeredBy="admin",
            mailRequest=_build_mail_request_notification_context(updated),
        )
        notification_status = _notification_status_from_notify_result(notify_result)
    except Exception as exc:
        _log_special_case_exception(user_id=member_id, exc=exc)
        notification_status = "FAILED"

    update_request_notification_status(
        request_id=request_id,
        status=notification_status,
        notification_at=notification_at,
    )

    refreshed = find_mail_request(request_id)
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
    request_doc = find_mail_request(request_id)
    if request_doc and request_doc.get("status") != "RESOLVED":
        request_doc = None
    if not request_doc:
        raise APIError(404, "mail request not found")

    member_id = request_doc.get("memberId")
    if not isinstance(member_id, ObjectId):
        raise APIError(500, "mail request has invalid member id")

    resolved_notifier = notifier or _default_special_case_notifier()
    notification_status: Literal["SENT", "SKIPPED", "FAILED"] = "FAILED"
    notification_at = _utcnow()
    try:
        notify_result = resolved_notifier.notifySpecialCase(
            userId=member_id,
            triggeredBy="admin",
            mailRequest=_build_mail_request_notification_context(request_doc),
        )
        notification_status = _notification_status_from_notify_result(notify_result)
    except Exception as exc:
        _log_special_case_exception(user_id=member_id, exc=exc)
        notification_status = "FAILED"

    update_request_notification_status(
        request_id=request_id,
        status=notification_status,
        notification_at=notification_at,
    )
    refreshed = find_mail_request(request_id)
    if not refreshed:
        raise APIError(500, "mail request missing after notification retry")
    return refreshed
