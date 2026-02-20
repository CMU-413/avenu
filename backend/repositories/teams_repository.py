from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from config import teams_collection, users_collection
from errors import APIError

from .common import run_in_transaction
from .mail_repository import delete_by_mailbox
from .mailboxes_repository import delete_mailbox, find_owner_mailbox, insert_mailbox, update_owner_display_name


def list_teams() -> list[dict[str, Any]]:
    return list(teams_collection.find())


def find_team(team_id: ObjectId, *, session: Any | None = None) -> dict[str, Any] | None:
    return teams_collection.find_one({"_id": team_id}, session=session)


def find_team_by_optix_id(optix_id: int) -> dict[str, Any] | None:
    return teams_collection.find_one({"optixId": optix_id})


def count_by_ids(team_ids: list[ObjectId], *, session: Any | None = None) -> int:
    if not team_ids:
        return 0
    return teams_collection.count_documents({"_id": {"$in": team_ids}}, session=session)


def insert_team(doc: dict[str, Any], *, session: Any | None = None) -> ObjectId:
    inserted = teams_collection.insert_one(doc, session=session)
    return inserted.inserted_id


def update_team(team_id: ObjectId, patch: dict[str, Any], *, session: Any | None = None) -> int:
    result = teams_collection.update_one({"_id": team_id}, {"$set": patch}, session=session)
    return result.matched_count


def delete_team(team_id: ObjectId, *, session: Any | None = None) -> None:
    teams_collection.delete_one({"_id": team_id}, session=session)


def create_team_with_mailbox(*, team_doc: dict[str, Any], mailbox_doc: dict[str, Any]) -> dict[str, Any]:
    def work(session: Any) -> dict[str, Any]:
        inserted_id = insert_team(team_doc, session=session)
        mailbox_doc["refId"] = inserted_id
        insert_mailbox(mailbox_doc, session=session)

        created = find_team(inserted_id, session=session)
        if not created:
            raise APIError(500, "failed to create team")
        return created

    return run_in_transaction(work)


def update_team_with_mailbox_sync(*, team_id: ObjectId, patch: dict[str, Any]) -> dict[str, Any]:
    def work(session: Any) -> dict[str, Any]:
        matched_count = update_team(team_id, patch, session=session)
        if matched_count == 0:
            raise APIError(404, "team not found")

        if "name" in patch:
            update_owner_display_name(
                owner_type="team",
                ref_id=team_id,
                display_name=patch["name"],
                updated_at=datetime.now(tz=timezone.utc),
                session=session,
            )

        updated = find_team(team_id, session=session)
        if not updated:
            raise APIError(500, "failed to fetch updated team")
        return updated

    return run_in_transaction(work)


def delete_team_cascade(*, team_id: ObjectId, prune_users: bool) -> None:
    if not prune_users and users_collection.find_one({"teamIds": team_id}, {"_id": 1}) is not None:
        raise APIError(409, "cannot delete team while users reference it")

    def work(session: Any) -> None:
        if prune_users:
            users_collection.update_many({"teamIds": team_id}, {"$pull": {"teamIds": team_id}}, session=session)
        mailbox = find_owner_mailbox("team", team_id, session=session)
        if mailbox:
            delete_by_mailbox(mailbox["_id"], session=session)
            delete_mailbox(mailbox["_id"], session=session)
        delete_team(team_id, session=session)

    run_in_transaction(work)
