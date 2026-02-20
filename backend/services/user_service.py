from __future__ import annotations

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from errors import APIError
from models import build_mailbox_doc, build_user_create, build_user_patch
from repositories.users_repository import (
    create_user_with_mailbox,
    find_user,
    find_user_by_email as repo_find_user_by_email,
    list_users as repo_list_users,
    update_user_with_mailbox_sync,
    delete_user_cascade,
)


def list_users() -> list[dict[str, Any]]:
    return repo_list_users()


def get_user(user_id: ObjectId) -> dict[str, Any] | None:
    return find_user(user_id)


def find_user_by_email(email: str) -> dict[str, Any] | None:
    return repo_find_user_by_email(email)


def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    user_doc = build_user_create(payload)
    mailbox = build_mailbox_doc(owner_type="user", ref_id=ObjectId(), display_name=user_doc["fullname"])

    try:
        return create_user_with_mailbox(user_doc=user_doc, mailbox_doc=mailbox)
    except DuplicateKeyError as exc:
        raise APIError(409, "user with same optixId or email already exists") from exc


def update_user(user_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_user_patch(payload)

    try:
        return update_user_with_mailbox_sync(user_id=user_id, patch=patch)
    except DuplicateKeyError as exc:
        raise APIError(409, "user with same optixId or email already exists") from exc


def delete_user(user_id: ObjectId) -> None:
    delete_user_cascade(user_id)
