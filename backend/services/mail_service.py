from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from errors import APIError
from models import build_mail_create, build_mail_patch
from models.builders import _optional_mail_piece_count
from repositories.mail_repository import (
    delete_mail as repo_delete_mail,
    find_mail as repo_find_mail,
    insert_mail,
    list_mail as repo_list_mail,
    update_mail as repo_update_mail,
)
from repositories.mailboxes_repository import mailbox_exists


def _ensure_mailbox_exists(mailbox_id: ObjectId) -> None:
    if not mailbox_exists(mailbox_id):
        raise APIError(422, "mailbox does not exist")


def list_mail(
    *,
    day_start: datetime | None = None,
    day_end: datetime | None = None,
    mailbox_id: ObjectId | None = None,
) -> list[dict[str, Any]]:
    return repo_list_mail(day_start=day_start, day_end=day_end, mailbox_id=mailbox_id)


def get_mail(mail_id: ObjectId) -> dict[str, Any] | None:
    return repo_find_mail(mail_id)


def create_mail(payload: dict[str, Any]) -> dict[str, Any]:
    """Create one or more mail docs (one per piece).

    If the payload carries a legacy ``count: N`` (N > 1) the service expands
    to N single-piece inserts so new writes always satisfy the
    one-doc-per-piece invariant. Returns the first inserted document so the
    HTTP contract (single resource created) is preserved.
    """
    doc = build_mail_create(payload)
    _ensure_mailbox_exists(doc["mailboxId"])
    n = _optional_mail_piece_count(payload) or 1
    first_id = None
    for _ in range(n):
        inserted_id = insert_mail(dict(doc))
        if first_id is None:
            first_id = inserted_id
    created = repo_find_mail(first_id) if first_id else None
    if not created:
        raise APIError(500, "failed to create mail")
    return created


def update_mail(mail_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    payload_eff = dict(payload)
    unset_count = False
    if "count" in payload_eff:
        n = _optional_mail_piece_count(payload_eff)
        if n == 1:
            unset_count = True
            del payload_eff["count"]
    patch = build_mail_patch(payload_eff)
    if "mailboxId" in patch:
        _ensure_mailbox_exists(patch["mailboxId"])

    matched_count = repo_update_mail(mail_id, patch, unset_count=unset_count)
    if matched_count == 0:
        raise APIError(404, "mail not found")
    updated = repo_find_mail(mail_id)
    if not updated:
        raise APIError(500, "failed to fetch updated mail")
    return updated


def delete_mail(mail_id: ObjectId) -> None:
    repo_delete_mail(mail_id)
