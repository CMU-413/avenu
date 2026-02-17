from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config import mail_collection, mailboxes_collection, teams_collection, users_collection
from errors import APIError
from models import build_mailbox_doc, build_user_create, build_user_patch
from repositories import find_user, start_txn


def list_users() -> list[dict[str, Any]]:
    return list(users_collection.find())


def get_user(user_id: ObjectId) -> dict[str, Any] | None:
    return find_user(user_id)


def find_user_by_email(email: str) -> dict[str, Any] | None:
    return users_collection.find_one({"email": email})


def _ensure_teams_exist(team_ids: list[ObjectId], *, session) -> None:
    if not team_ids:
        return
    found = teams_collection.count_documents({"_id": {"$in": team_ids}}, session=session)
    if found != len(team_ids):
        raise APIError(422, "one or more teamIds do not exist")


def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    user_doc = build_user_create(payload)

    def work(session):
        _ensure_teams_exist(user_doc["teamIds"], session=session)
        inserted = users_collection.insert_one(user_doc, session=session)
        user_id = inserted.inserted_id
        mailbox = build_mailbox_doc(owner_type="user", ref_id=user_id, display_name=user_doc["fullname"])
        mailboxes_collection.insert_one(mailbox, session=session)
        created = users_collection.find_one({"_id": user_id}, session=session)
        if not created:
            raise APIError(500, "failed to create user")
        return created

    try:
        return start_txn(work)
    except DuplicateKeyError as exc:
        raise APIError(409, "user with same optixId or email already exists") from exc


def update_user(user_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_user_patch(payload)

    def work(session):
        if "teamIds" in patch:
            _ensure_teams_exist(patch["teamIds"], session=session)
        result = users_collection.update_one({"_id": user_id}, {"$set": patch}, session=session)
        if result.matched_count == 0:
            raise APIError(404, "user not found")
        if "fullname" in patch:
            mailboxes_collection.update_one(
                {"type": "user", "refId": user_id},
                {"$set": {"displayName": patch["fullname"], "updatedAt": datetime.now(tz=timezone.utc)}},
                session=session,
            )
        updated = users_collection.find_one({"_id": user_id}, session=session)
        if not updated:
            raise APIError(500, "failed to fetch updated user")
        return updated

    try:
        return start_txn(work)
    except DuplicateKeyError as exc:
        raise APIError(409, "user with same optixId or email already exists") from exc


def delete_user(user_id: ObjectId) -> None:
    def work(session):
        mailbox = mailboxes_collection.find_one({"type": "user", "refId": user_id}, session=session)
        if mailbox:
            mail_collection.delete_many({"mailboxId": mailbox["_id"]}, session=session)
            mailboxes_collection.delete_one({"_id": mailbox["_id"]}, session=session)
        users_collection.delete_one({"_id": user_id}, session=session)

    start_txn(work)
