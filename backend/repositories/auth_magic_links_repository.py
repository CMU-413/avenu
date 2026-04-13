from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import auth_magic_links_collection


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def get_magic_link(token_id: str) -> dict[str, Any] | None:
    doc = auth_magic_links_collection.find_one({"tokenId": token_id})
    if not doc:
        return None
    return {
        "user_id": doc["userId"],
        "exp": doc["exp"],
        "metadata": doc.get("metadata", {}),
        "consumed": doc.get("consumed", False),
        "created_at": doc["createdAt"],
    }


def put_magic_link(token_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow()
    doc = {
        "tokenId": token_id,
        "userId": data["user_id"],
        "exp": data["exp"],
        "expiresAt": datetime.fromtimestamp(data["exp"], tz=timezone.utc),
        "metadata": data.get("metadata", {}),
        "consumed": data.get("consumed", False),
        "createdAt": _coerce_created_at(data.get("created_at"), now),
        "updatedAt": now,
    }
    auth_magic_links_collection.update_one({"tokenId": token_id}, {"$set": doc}, upsert=True)
    return {
        "user_id": doc["userId"],
        "exp": doc["exp"],
        "metadata": doc["metadata"],
        "consumed": doc["consumed"],
        "created_at": doc["createdAt"],
    }


def _coerce_created_at(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return fallback
