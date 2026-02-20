from __future__ import annotations

from typing import Any

from bson import ObjectId

from errors import APIError
from repositories.mailboxes_repository import (
    find_member_mailbox,
    list_member_mailboxes as repo_list_member_mailboxes,
    member_mailbox_scope,
)


def member_mailbox_scope(user: dict[str, Any]) -> dict[str, Any]:
    team_ids = user.get("teamIds") if isinstance(user.get("teamIds"), list) else []
    mailbox_or: list[dict[str, Any]] = [{"type": "user", "refId": user["_id"]}]
    if team_ids:
        mailbox_or.append({"type": "team", "refId": {"$in": team_ids}})
    return {"$or": mailbox_or}


def list_member_mailboxes(user: dict[str, Any]) -> list[dict[str, Any]]:
    return repo_list_member_mailboxes(user)


def assert_member_mailbox_access(user: dict[str, Any], mailbox_id: ObjectId) -> dict[str, Any]:
    mailbox = find_member_mailbox(user, mailbox_id)
    if mailbox is None:
        raise APIError(403, "forbidden")
    return mailbox
