from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from bson import ObjectId

from config import (
    client,
    idempotency_keys_collection,
    mail_collection,
    mail_requests_collection,
    mailboxes_collection,
    teams_collection,
    users_collection,
)


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


def start_txn(work: Callable[[Any], Any]) -> Any:
    with client.start_session() as session:
        with session.start_transaction():
            return work(session)


def find_user(user_id: ObjectId):
    return users_collection.find_one({"_id": user_id})


def find_user_by_optix_id(optix_id: int):
    return users_collection.find_one({"optixId": optix_id})


def find_team(team_id: ObjectId):
    return teams_collection.find_one({"_id": team_id})


def find_team_by_optix_id(optix_id: int):
    return teams_collection.find_one({"optixId": optix_id})


def find_mailbox(mailbox_id: ObjectId):
    return mailboxes_collection.find_one({"_id": mailbox_id})


def find_mail(mail_id: ObjectId):
    return mail_collection.find_one({"_id": mail_id})


def find_mail_request(mail_request_id: ObjectId):
    return mail_requests_collection.find_one({"_id": mail_request_id})


def owner_mailbox(owner_type: str, ref_id: ObjectId):
    return mailboxes_collection.find_one({"type": owner_type, "refId": ref_id})


def has_users_with_team(team_id: ObjectId) -> bool:
    return users_collection.find_one({"teamIds": team_id}, {"_id": 1}) is not None


def insert_idempotency(doc: dict[str, Any]):
    return idempotency_keys_collection.insert_one(doc)
