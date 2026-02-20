from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from flask import request

from errors import APIError
from validators import parse_object_id, require_dict


def json_payload() -> dict[str, Any]:
    return require_dict(request.get_json(silent=True))


def parse_day_utc(date_value: str) -> tuple[datetime, datetime]:
    try:
        day = datetime.strptime(date_value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise APIError(422, "date must be YYYY-MM-DD") from exc
    return day, day + timedelta(days=1)


def parse_iso_date(value: str, *, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise APIError(422, f"{field_name} must be YYYY-MM-DD") from exc


def parse_optional_object_id_filter(value: str | None, *, field_name: str) -> ObjectId | None:
    if value is None:
        return None
    if not ObjectId.is_valid(value):
        raise APIError(422, f"{field_name} must be a valid ObjectId string")
    return ObjectId(value)


def parse_required_object_id(value: str, field_name: str) -> ObjectId:
    return parse_object_id(value, field_name)
