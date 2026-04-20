from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from config import login_rate_limit_collection


def record_login_attempt(
    *,
    scope: str,
    key: str,
    window_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_now = _coerce_utc(now)
    normalized_scope = scope.strip().lower()
    normalized_key = key.strip().lower()
    window_start = _window_start(resolved_now, window_seconds)
    expires_at = window_start + timedelta(seconds=window_seconds)
    doc = login_rate_limit_collection.find_one_and_update(
        {
            "scope": normalized_scope,
            "key": normalized_key,
            "windowStart": window_start,
        },
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "scope": normalized_scope,
                "key": normalized_key,
                "windowSeconds": window_seconds,
                "windowStart": window_start,
                "expiresAt": expires_at,
                "createdAt": resolved_now,
            },
            "$set": {
                "updatedAt": resolved_now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _to_attempt_bucket(doc)


def _to_attempt_bucket(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": doc["scope"],
        "key": doc["key"],
        "count": doc["count"],
        "windowSeconds": doc["windowSeconds"],
        "windowStart": doc["windowStart"],
        "expiresAt": doc["expiresAt"],
        "createdAt": doc["createdAt"],
        "updatedAt": doc["updatedAt"],
    }


def _coerce_utc(value: datetime | None) -> datetime:
    resolved = value or datetime.now(tz=timezone.utc)
    if resolved.tzinfo is None:
        return resolved.replace(tzinfo=timezone.utc)
    return resolved.astimezone(timezone.utc)


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch_seconds = int(now.timestamp())
    bucket_seconds = epoch_seconds - (epoch_seconds % window_seconds)
    return datetime.fromtimestamp(bucket_seconds, tz=timezone.utc)
