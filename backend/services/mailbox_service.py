from __future__ import annotations

from typing import Any

from bson import ObjectId

from errors import APIError
from models import build_mailbox_patch
from repositories.mailboxes_repository import (
    find_mailbox,
    list_mailboxes as repo_list_mailboxes,
    update_mailbox as repo_update_mailbox,
)


def list_mailboxes() -> list[dict[str, Any]]:
    return repo_list_mailboxes()


def get_mailbox(mailbox_id: ObjectId) -> dict[str, Any] | None:
    return find_mailbox(mailbox_id)


def update_mailbox(mailbox_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_mailbox_patch(payload)
    matched_count = repo_update_mailbox(mailbox_id, patch)
    if matched_count == 0:
        raise APIError(404, "mailbox not found")
    updated = find_mailbox(mailbox_id)
    if not updated:
        raise APIError(500, "failed to fetch updated mailbox")
    return updated
