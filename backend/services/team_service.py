from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from errors import APIError
from models import build_mailbox_doc, build_team_create, build_team_patch
from repositories.teams_repository import (
    create_team_with_mailbox,
    delete_team_cascade,
    find_team,
    list_teams as repo_list_teams,
    update_team_with_mailbox_sync,
)


def list_teams() -> list[dict[str, Any]]:
    return repo_list_teams()


def get_team(team_id: ObjectId) -> dict[str, Any] | None:
    return find_team(team_id)


def create_team(payload: dict[str, Any]) -> dict[str, Any]:
    team_doc = build_team_create(payload)
    mailbox = build_mailbox_doc(owner_type="team", ref_id=ObjectId(), display_name=team_doc["name"])

    try:
        return create_team_with_mailbox(team_doc=team_doc, mailbox_doc=mailbox)
    except DuplicateKeyError as exc:
        raise APIError(409, "team with same optixId already exists") from exc


def update_team(team_id: ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
    patch = build_team_patch(payload)

    try:
        return update_team_with_mailbox_sync(team_id=team_id, patch=patch)
    except DuplicateKeyError as exc:
        raise APIError(409, "team with same optixId already exists") from exc


def delete_team(team_id: ObjectId, *, prune_users: bool) -> None:
    delete_team_cascade(team_id=team_id, prune_users=prune_users)
