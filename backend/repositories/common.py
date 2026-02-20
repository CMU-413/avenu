from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from bson import ObjectId

from config import client


def to_api_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, list):
            out[key] = [str(v) if isinstance(v, ObjectId) else v for v in value]
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    if "_id" in out:
        out["id"] = out.pop("_id")
    return out


def run_in_transaction(work: Callable[[Any], Any]) -> Any:
    with client.start_session() as session:
        with session.start_transaction():
            return work(session)
