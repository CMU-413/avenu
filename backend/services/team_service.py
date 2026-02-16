from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config import mail_collection, mailboxes_collection, teams_collection, users_collection
from errors import APIError
from models import build_mailbox_doc, build_team_create, build_team_patch
from repositories import has_users_with_team, start_txn


def list_teams() -> list[dict[str, Any]]:
    return list(teams_collection.find())


def get_team(team_id: ObjectId) -> dict[str, Any] | None:
    return teams_collection.find_one({"_id": team_id})


def create_team(payload: dict[str, Any]) -> dict[str, Any]:
    team_doc = build_team_create(payload)

    def work(session):
        inserted = teams_collection.insert_one(team_doc, session=session)
        team_id = inserted.inserted_id
        mailbox = build_mailbox_doc(owner_type="team", ref_id=team_id, display_name=team_doc["name"])
        mailboxes_collection.insert_one(mailbox, session=session)
        created = teams_collection.find_one({"_id": team_id}, session=session)
        if not created:
            raise APIError(500, "failed to create team")
        return created

    try:
        return start_txn(work)
    except DuplicateKeyError as exc:
        raise APIError(409, "team with same optixId already exists") from exc


def update_team(team_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_team_patch(payload)

    def work(session):
        result = teams_collection.update_one({"_id": team_id}, {"$set": patch}, session=session)
        if result.matched_count == 0:
            raise APIError(404, "team not found")
        if "name" in patch:
            mailboxes_collection.update_one(
                {"type": "team", "refId": team_id},
                {"$set": {"displayName": patch["name"], "updatedAt": datetime.now(tz=timezone.utc)}},
                session=session,
            )
        updated = teams_collection.find_one({"_id": team_id}, session=session)
        if not updated:
            raise APIError(500, "failed to fetch updated team")
        return updated

    try:
        return start_txn(work)
    except DuplicateKeyError as exc:
        raise APIError(409, "team with same optixId already exists") from exc


def delete_team(team_id: ObjectId, *, prune_users: bool) -> None:
    if not prune_users and has_users_with_team(team_id):
        raise APIError(409, "cannot delete team while users reference it")

    def work(session):
        if prune_users:
            users_collection.update_many({"teamIds": team_id}, {"$pull": {"teamIds": team_id}}, session=session)
        mailbox = mailboxes_collection.find_one({"type": "team", "refId": team_id}, session=session)
        if mailbox:
            mail_collection.delete_many({"mailboxId": mailbox["_id"]}, session=session)
            mailboxes_collection.delete_one({"_id": mailbox["_id"]}, session=session)
        teams_collection.delete_one({"_id": team_id}, session=session)

    start_txn(work)
