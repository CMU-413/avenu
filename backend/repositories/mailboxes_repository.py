from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from config import mailboxes_collection
from errors import APIError


def member_mailbox_scope(user: dict[str, Any]) -> dict[str, Any]:
    team_ids = user.get("teamIds") if isinstance(user.get("teamIds"), list) else []
    mailbox_or: list[dict[str, Any]] = [{"type": "user", "refId": user["_id"]}]
    if team_ids:
        mailbox_or.append({"type": "team", "refId": {"$in": team_ids}})
    return {"$or": mailbox_or}


def list_mailboxes() -> list[dict[str, Any]]:
    return list(mailboxes_collection.find())


def find_mailbox(mailbox_id: ObjectId, *, session: Any | None = None) -> dict[str, Any] | None:
    return mailboxes_collection.find_one({"_id": mailbox_id}, session=session)


def mailbox_exists(mailbox_id: ObjectId) -> bool:
    return mailboxes_collection.find_one({"_id": mailbox_id}, {"_id": 1}) is not None


def insert_mailbox(doc: dict[str, Any], *, session: Any | None = None) -> ObjectId:
    inserted = mailboxes_collection.insert_one(doc, session=session)
    return inserted.inserted_id


def update_mailbox(mailbox_id: ObjectId, patch: dict[str, Any], *, session: Any | None = None) -> int:
    result = mailboxes_collection.update_one({"_id": mailbox_id}, {"$set": patch}, session=session)
    return result.matched_count


def update_owner_display_name(
    *, owner_type: str, ref_id: ObjectId, display_name: str, updated_at: datetime, session: Any | None = None
) -> None:
    mailboxes_collection.update_one(
        {"type": owner_type, "refId": ref_id},
        {"$set": {"displayName": display_name, "updatedAt": updated_at}},
        session=session,
    )


def find_owner_mailbox(owner_type: str, ref_id: ObjectId, *, session: Any | None = None) -> dict[str, Any] | None:
    return mailboxes_collection.find_one({"type": owner_type, "refId": ref_id}, session=session)


def delete_mailbox(mailbox_id: ObjectId, *, session: Any | None = None) -> None:
    mailboxes_collection.delete_one({"_id": mailbox_id}, session=session)


def list_member_mailboxes(user: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mailboxes_collection.find(member_mailbox_scope(user)).sort([("displayName", 1), ("_id", 1)]))


def find_member_mailbox(user: dict[str, Any], mailbox_id: ObjectId) -> dict[str, Any] | None:
    query = {"_id": mailbox_id, **member_mailbox_scope(user)}
    return mailboxes_collection.find_one(query)


def require_member_mailbox(user: dict[str, Any], mailbox_id: ObjectId) -> dict[str, Any]:
    mailbox = find_member_mailbox(user, mailbox_id)
    if mailbox is None:
        raise APIError(403, "forbidden")
    return mailbox


def list_by_scope(scope_query: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mailboxes_collection.find(scope_query).sort([("displayName", 1), ("_id", 1)]))
