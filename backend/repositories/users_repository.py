from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from config import users_collection
from errors import APIError

from .common import run_in_transaction
from .mail_repository import delete_by_mailbox
from .mailboxes_repository import delete_mailbox, find_owner_mailbox, insert_mailbox, update_owner_display_name
from .teams_repository import count_by_ids


def list_users() -> list[dict[str, Any]]:
    return list(users_collection.find())


def find_user(user_id: ObjectId, *, session: Any | None = None) -> dict[str, Any] | None:
    return users_collection.find_one({"_id": user_id}, session=session)


def find_user_by_email(email: str) -> dict[str, Any] | None:
    return users_collection.find_one({"email": email})


def find_user_by_optix_id(optix_id: int) -> dict[str, Any] | None:
    return users_collection.find_one({"optixId": optix_id})


def count_by_team_ids(team_ids: list[ObjectId], *, session: Any | None = None) -> int:
    if not team_ids:
        return 0
    return users_collection.count_documents({"teamIds": {"$in": team_ids}}, session=session)


def has_users_with_team(team_id: ObjectId) -> bool:
    return users_collection.find_one({"teamIds": team_id}, {"_id": 1}) is not None


def insert_user(doc: dict[str, Any], *, session: Any | None = None) -> ObjectId:
    inserted = users_collection.insert_one(doc, session=session)
    return inserted.inserted_id


def update_user(user_id: ObjectId, patch: dict[str, Any], *, session: Any | None = None) -> int:
    result = users_collection.update_one({"_id": user_id}, {"$set": patch}, session=session)
    return result.matched_count


def delete_user(user_id: ObjectId, *, session: Any | None = None) -> None:
    users_collection.delete_one({"_id": user_id}, session=session)


def pull_team_from_users(team_id: ObjectId, *, session: Any | None = None) -> None:
    users_collection.update_many({"teamIds": team_id}, {"$pull": {"teamIds": team_id}}, session=session)


def list_opted_in_user_ids(*, preference: str = "email") -> list[ObjectId]:
    return [doc["_id"] for doc in users_collection.find({"notifPrefs": {"$in": [preference]}}, {"_id": 1})]


def update_notif_prefs(user_id: ObjectId, prefs: list[str], *, updated_at: datetime) -> None:
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {"notifPrefs": prefs, "updatedAt": updated_at}},
    )


def find_for_notification(user_id: ObjectId) -> dict[str, Any] | None:
    return users_collection.find_one({"_id": user_id}, {"email": 1, "fullname": 1, "notifPrefs": 1})


def find_basic_profile(user_id: ObjectId) -> dict[str, Any] | None:
    return users_collection.find_one({"_id": user_id}, {"email": 1, "fullname": 1})


def create_user_with_mailbox(*, user_doc: dict[str, Any], mailbox_doc: dict[str, Any]) -> dict[str, Any]:
    def work(session: Any) -> dict[str, Any]:
        if user_doc.get("teamIds"):
            found = count_by_ids(user_doc["teamIds"], session=session)
            if found != len(user_doc["teamIds"]):
                raise APIError(422, "one or more teamIds do not exist")

        inserted_id = insert_user(user_doc, session=session)
        mailbox_doc["refId"] = inserted_id
        insert_mailbox(mailbox_doc, session=session)

        created = find_user(inserted_id, session=session)
        if not created:
            raise APIError(500, "failed to create user")
        return created

    return run_in_transaction(work)


def update_user_with_mailbox_sync(*, user_id: ObjectId, patch: dict[str, Any]) -> dict[str, Any]:
    def work(session: Any) -> dict[str, Any]:
        if "teamIds" in patch:
            found = count_by_ids(patch["teamIds"], session=session)
            if found != len(patch["teamIds"]):
                raise APIError(422, "one or more teamIds do not exist")

        matched_count = update_user(user_id, patch, session=session)
        if matched_count == 0:
            raise APIError(404, "user not found")

        if "fullname" in patch:
            update_owner_display_name(
                owner_type="user",
                ref_id=user_id,
                display_name=patch["fullname"],
                updated_at=datetime.now(tz=timezone.utc),
                session=session,
            )

        updated = find_user(user_id, session=session)
        if not updated:
            raise APIError(500, "failed to fetch updated user")
        return updated

    return run_in_transaction(work)


def delete_user_cascade(user_id: ObjectId) -> None:
    def work(session: Any) -> None:
        mailbox = find_owner_mailbox("user", user_id, session=session)
        if mailbox:
            delete_by_mailbox(mailbox["_id"], session=session)
            delete_mailbox(mailbox["_id"], session=session)
        delete_user(user_id, session=session)

    run_in_transaction(work)
