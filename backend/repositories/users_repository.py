from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config import users_collection
from errors import APIError
from models import build_mailbox_doc, build_user_create, build_user_patch

from .common import run_in_transaction
from .mail_repository import delete_by_mailbox
from .mailboxes_repository import delete_mailbox, find_owner_mailbox, insert_mailbox, update_owner_display_name
from .teams_repository import count_by_ids
from services.user_preferences import normalize_effective_notification_state

DEFAULT_EXTERNAL_IDENTITY_NOTIF_PREFS = ["email"]


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
    return list_weekly_summary_candidate_user_ids(preferences=[preference])


def list_weekly_summary_candidate_user_ids(*, preferences: list[str]) -> list[ObjectId]:
    normalized = sorted({item.strip() for item in preferences if isinstance(item, str) and item.strip()})
    if not normalized:
        return []
    return [doc["_id"] for doc in users_collection.find({"notifPrefs": {"$in": normalized}}, {"_id": 1})]


def update_notif_prefs(user_id: ObjectId, prefs: list[str], *, updated_at: datetime) -> None:
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {"notifPrefs": prefs, "updatedAt": updated_at}},
    )


def find_for_notification(user_id: ObjectId) -> dict[str, Any] | None:
    return users_collection.find_one({"_id": user_id}, {"email": 1, "fullname": 1, "phone": 1, "notifPrefs": 1})


def find_basic_profile(user_id: ObjectId) -> dict[str, Any] | None:
    return users_collection.find_one({"_id": user_id}, {"email": 1, "fullname": 1, "phone": 1, "notifPrefs": 1})


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


def upsert_user_from_external_identity(
    *,
    optix_id: int,
    fullname: str,
    email: str,
    phone: str,
    is_admin: bool,
    team_ids: list[ObjectId],
) -> tuple[dict[str, Any], bool]:
    existing = find_user_by_optix_id(optix_id)
    if existing is None:
        user_doc = build_user_create(
            {
                "optixId": optix_id,
                "fullname": fullname,
                "email": email,
                "phone": phone,
                "isAdmin": is_admin,
                "teamIds": team_ids,
                "notifPrefs": DEFAULT_EXTERNAL_IDENTITY_NOTIF_PREFS,
            }
        )
        mailbox_doc = build_mailbox_doc(owner_type="user", ref_id=ObjectId(), display_name=user_doc["fullname"])
        try:
            created = create_user_with_mailbox(user_doc=user_doc, mailbox_doc=mailbox_doc)
            return created, True
        except DuplicateKeyError as exc:
            raise APIError(409, "user with same optixId or email already exists") from exc

    candidate_patch = build_user_patch(
        {
            "fullname": fullname,
            "email": email,
            "phone": phone,
            "isAdmin": is_admin,
            "teamIds": team_ids,
        }
    )
    patch: dict[str, Any] = {}
    for key in ("fullname", "email", "phone", "isAdmin"):
        if existing.get(key) != candidate_patch.get(key):
            patch[key] = candidate_patch[key]

    if "phone" in patch:
        normalized = normalize_effective_notification_state(
            current_user=existing,
            phone_patch=candidate_patch["phone"],
        )
        if normalized["notifPrefs"] != existing.get("notifPrefs", []):
            patch["notifPrefs"] = normalized["notifPrefs"]

    current_team_ids = {str(team_id) for team_id in existing.get("teamIds", [])}
    next_team_ids = {str(team_id) for team_id in candidate_patch.get("teamIds", [])}
    if current_team_ids != next_team_ids:
        patch["teamIds"] = candidate_patch["teamIds"]

    if not patch:
        return existing, False

    patch["updatedAt"] = candidate_patch["updatedAt"]
    try:
        updated = update_user_with_mailbox_sync(user_id=existing["_id"], patch=patch)
        return updated, False
    except DuplicateKeyError as exc:
        raise APIError(409, "user with same optixId or email already exists") from exc
