from __future__ import annotations

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


def list_member_mailboxes(user: dict[str, Any]) -> list[dict[str, Any]]:
    return list(mailboxes_collection.find(member_mailbox_scope(user)).sort([("displayName", 1), ("_id", 1)]))


def assert_member_mailbox_access(user: dict[str, Any], mailbox_id: ObjectId) -> dict[str, Any]:
    query = {"_id": mailbox_id, **member_mailbox_scope(user)}
    mailbox = mailboxes_collection.find_one(query)
    if mailbox is None:
        raise APIError(403, "forbidden")
    return mailbox
