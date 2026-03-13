from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from errors import APIError
from validators import (
    normalize_email,
    optional_bool,
    optional_phone,
    optional_string,
    parse_distinct_object_ids,
    parse_enum_set,
    parse_iso_datetime,
    require_positive_int,
    require_string,
)

NOTIF_PREFS = {"email", "text"}
MAILBOX_TYPES = {"user", "team"}
MAIL_TYPES = {"letter", "package"}
MAIL_REQUEST_STATUSES = {"ACTIVE", "CANCELLED", "RESOLVED"}
MAIL_REQUEST_NOTIFICATION_STATUSES = {"SENT", "FAILED"}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _optional_text(payload: dict[str, Any], key: str, max_len: int) -> str | None:
    """Optional string field; allows empty. Returns None if key absent."""
    if key not in payload or payload[key] is None:
        return None
    value = payload.get(key)
    if not isinstance(value, str):
        raise APIError(422, f"{key} must be a string")
    stripped = value.strip()
    if len(stripped) > max_len:
        raise APIError(422, f"{key} exceeds max length")
    return stripped


def _parse_optional_iso_day(payload: dict[str, Any], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise APIError(422, f"{key} must be YYYY-MM-DD")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise APIError(422, f"{key} must be YYYY-MM-DD") from exc
    return parsed.isoformat()


def build_user_create(payload: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow()
    email = normalize_email(require_string(payload, "email", max_len=320))
    return {
        "optixId": require_positive_int(payload, "optixId"),
        "isAdmin": optional_bool(payload, "isAdmin", default=False),
        "fullname": require_string(payload, "fullname"),
        "email": email,
        "phone": optional_phone(payload.get("phone")),
        "teamIds": parse_distinct_object_ids(payload.get("teamIds"), "teamIds"),
        "notifPrefs": parse_enum_set(payload.get("notifPrefs"), field_name="notifPrefs", allowed=NOTIF_PREFS),
        "createdAt": now,
        "updatedAt": now,
    }


def build_user_patch(payload: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "isAdmin" in payload:
        patch["isAdmin"] = optional_bool(payload, "isAdmin")
    if "fullname" in payload:
        patch["fullname"] = require_string(payload, "fullname")
    if "email" in payload:
        patch["email"] = normalize_email(require_string(payload, "email", max_len=320))
    if "phone" in payload:
        patch["phone"] = optional_phone(payload.get("phone"))
    if "teamIds" in payload:
        patch["teamIds"] = parse_distinct_object_ids(payload.get("teamIds"), "teamIds")
    if "notifPrefs" in payload:
        patch["notifPrefs"] = parse_enum_set(payload.get("notifPrefs"), field_name="notifPrefs", allowed=NOTIF_PREFS)
    if not patch:
        raise APIError(400, "no update payload provided")
    patch["updatedAt"] = _utcnow()
    return patch


def build_team_create(payload: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow()
    return {
        "optixId": require_positive_int(payload, "optixId"),
        "name": require_string(payload, "name"),
        "createdAt": now,
        "updatedAt": now,
    }


def build_team_patch(payload: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "name" in payload:
        patch["name"] = require_string(payload, "name")
    if "optixId" in payload:
        patch["optixId"] = require_positive_int(payload, "optixId")
    if not patch:
        raise APIError(400, "no update payload provided")
    patch["updatedAt"] = _utcnow()
    return patch


def build_mailbox_patch(payload: dict[str, Any]) -> dict[str, Any]:
    if "displayName" not in payload:
        raise APIError(400, "no update payload provided")
    patch = {
        "displayName": require_string(payload, "displayName"),
        "updatedAt": _utcnow(),
    }
    return patch


def build_mail_create(payload: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow()
    mailbox_id = payload.get("mailboxId")
    if not isinstance(mailbox_id, str) or not ObjectId.is_valid(mailbox_id):
        raise APIError(422, "mailboxId must be a valid ObjectId string")

    mail_type = payload.get("type")
    if mail_type not in MAIL_TYPES:
        raise APIError(422, f"type must be one of {sorted(MAIL_TYPES)}")

    doc: dict[str, Any] = {
        "mailboxId": ObjectId(mailbox_id),
        "date": parse_iso_datetime(payload, "date"),
        "type": mail_type,
        "createdAt": now,
        "updatedAt": now,
    }
    receiver = _optional_text(payload, "receiverName", 2000)
    if receiver is not None:
        doc["receiverName"] = receiver
    sender = _optional_text(payload, "senderInfo", 500)
    if sender is not None:
        doc["senderInfo"] = sender
    return doc


def build_mail_patch(payload: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}

    if "mailboxId" in payload:
        mailbox_id = payload.get("mailboxId")
        if not isinstance(mailbox_id, str) or not ObjectId.is_valid(mailbox_id):
            raise APIError(422, "mailboxId must be a valid ObjectId string")
        patch["mailboxId"] = ObjectId(mailbox_id)

    if "date" in payload:
        patch["date"] = parse_iso_datetime(payload, "date")

    if "type" in payload:
        mail_type = payload.get("type")
        if mail_type not in MAIL_TYPES:
            raise APIError(422, f"type must be one of {sorted(MAIL_TYPES)}")
        patch["type"] = mail_type

    if "receiverName" in payload:
        patch["receiverName"] = _optional_text(payload, "receiverName", 2000)
    if "senderInfo" in payload:
        patch["senderInfo"] = _optional_text(payload, "senderInfo", 500)

    if not patch:
        raise APIError(400, "no update payload provided")

    patch["updatedAt"] = _utcnow()
    return patch


def build_mailbox_doc(*, owner_type: str, ref_id: ObjectId, display_name: str) -> dict[str, Any]:
    if owner_type not in MAILBOX_TYPES:
        raise APIError(500, "invalid mailbox owner type")
    now = _utcnow()
    return {
        "type": owner_type,
        "refId": ref_id,
        "displayName": display_name,
        "createdAt": now,
        "updatedAt": now,
    }


def build_mail_request_create(payload: dict[str, Any], *, member_id: ObjectId) -> dict[str, Any]:
    now = _utcnow()
    mailbox_id = payload.get("mailboxId")
    if not isinstance(mailbox_id, str) or not ObjectId.is_valid(mailbox_id):
        raise APIError(422, "mailboxId must be a valid ObjectId string")

    expected_sender = optional_string(payload, "expectedSender")
    description = optional_string(payload, "description", max_len=1000)
    if expected_sender is None and description is None:
        raise APIError(400, "expectedSender or description is required")

    start_date = _parse_optional_iso_day(payload, "startDate")
    end_date = _parse_optional_iso_day(payload, "endDate")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise APIError(400, "endDate must be on or after startDate")

    return {
        "mailboxId": ObjectId(mailbox_id),
        "memberId": member_id,
        "expectedSender": expected_sender,
        "description": description,
        "startDate": start_date,
        "endDate": end_date,
        "status": "ACTIVE",
        "resolvedAt": None,
        "resolvedBy": None,
        "lastNotificationStatus": None,
        "lastNotificationAt": None,
        "createdAt": now,
        "updatedAt": now,
    }
