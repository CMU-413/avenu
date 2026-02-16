from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from errors import APIError


TTL_HOURS = 24


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_idempotency_key(headers: dict[str, str]) -> str:
    key = headers.get("Idempotency-Key") or headers.get("idempotency-key")
    if not key:
        raise APIError(400, "Idempotency-Key header is required")
    return key.strip()


def reserve_or_replay(
    collection: Collection,
    *,
    key: str,
    route: str,
    method: str,
    request_hash: str,
) -> dict[str, Any] | None:
    now = datetime.now(tz=timezone.utc)
    doc = {
        "key": key,
        "route": route,
        "method": method,
        "requestHash": request_hash,
        "responseStatus": None,
        "responseBody": None,
        "createdAt": now,
        "expiresAt": now + timedelta(hours=TTL_HOURS),
    }
    try:
        collection.insert_one(doc)
        return None
    except DuplicateKeyError:
        existing = collection.find_one({"key": key, "route": route, "method": method})
        if not existing:
            raise APIError(409, "idempotency key conflict")
        if existing.get("requestHash") != request_hash:
            raise APIError(409, "Idempotency-Key reuse with different payload")
        if existing.get("responseStatus") is None:
            raise APIError(409, "Idempotency-Key request is currently in progress")
        return {
            "status": existing["responseStatus"],
            "body": existing["responseBody"],
        }


def store_idempotent_response(
    collection: Collection,
    *,
    key: str,
    route: str,
    method: str,
    status: int,
    body: dict[str, Any],
) -> None:
    collection.update_one(
        {"key": key, "route": route, "method": method},
        {"$set": {"responseStatus": status, "responseBody": body}},
    )
