from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from errors import APIError


def parse_object_id(value: str, field_name: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise APIError(400, f"invalid {field_name}")
    return ObjectId(value)


def require_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise APIError(400, "invalid json payload")
    return payload


def require_string(payload: dict[str, Any], key: str, *, max_len: int = 200) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise APIError(422, f"{key} must be a string")
    value = value.strip()
    if not value:
        raise APIError(422, f"{key} is required")
    if len(value) > max_len:
        raise APIError(422, f"{key} exceeds max length")
    return value


def optional_string(payload: dict[str, Any], key: str, *, max_len: int = 200) -> str | None:
    if key not in payload or payload[key] is None:
        return None
    return require_string(payload, key, max_len=max_len)


def require_positive_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise APIError(422, f"{key} must be a positive integer")
    return value


def optional_bool(payload: dict[str, Any], key: str, *, default: bool = False) -> bool:
    if key not in payload:
        return default
    value = payload[key]
    if not isinstance(value, bool):
        raise APIError(422, f"{key} must be a boolean")
    return value


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise APIError(422, "email must be valid")
    return normalized


def optional_phone(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise APIError(422, "phone must be a string")
    phone = value.strip()
    if not phone:
        return None
    if not phone.startswith("+") or not phone[1:].isdigit():
        raise APIError(422, "phone must use E.164 format")
    return phone


def parse_distinct_object_ids(values: Any, field_name: str) -> list[ObjectId]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise APIError(422, f"{field_name} must be an array")

    unique_ids: list[ObjectId] = []
    seen: set[ObjectId] = set()
    for raw in values:
        if isinstance(raw, ObjectId):
            oid = raw
        elif isinstance(raw, str) and ObjectId.is_valid(raw):
            oid = ObjectId(raw)
        else:
            raise APIError(422, f"{field_name} must contain valid ObjectIds")
        if oid not in seen:
            seen.add(oid)
            unique_ids.append(oid)
    return unique_ids


def parse_enum_set(values: Any, *, field_name: str, allowed: set[str]) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise APIError(422, f"{field_name} must be an array")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str) or raw not in allowed:
            raise APIError(422, f"{field_name} must contain only {sorted(allowed)}")
        if raw not in seen:
            seen.add(raw)
            normalized.append(raw)
    return normalized


def parse_iso_datetime(payload: dict[str, Any], key: str) -> datetime:
    raw = payload.get(key)
    if not isinstance(raw, str):
        raise APIError(422, f"{key} must be an ISO-8601 string")
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise APIError(422, f"{key} must be an ISO-8601 string") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
