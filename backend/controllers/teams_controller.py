from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request

from controllers.auth_guard import require_admin_session
from controllers.common import json_payload, parse_required_object_id
from errors import APIError
from idempotency import payload_hash, require_idempotency_key
from repositories import to_api_doc
from repositories.idempotency_repository import delete_reservation, reserve_or_replay_request, store_response
from services.team_service import create_team, delete_team, get_team, list_teams, update_team

teams_bp = Blueprint("teams", __name__)


def _idempotent_create(
    *,
    route: str,
    create_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    payload = json_payload()
    key = require_idempotency_key(request.headers)
    request_hash = payload_hash(payload)

    replay = reserve_or_replay_request(
        key=key,
        route=route,
        method="POST",
        request_hash=request_hash,
    )
    if replay is not None:
        return replay["body"], replay["status"]

    try:
        created = create_fn(payload)
        body = to_api_doc(created)
        if body is None:
            raise APIError(500, "failed to build response")
        store_response(
            key=key,
            route=route,
            method="POST",
            status=201,
            body=body,
        )
        return body, 201
    except Exception:
        delete_reservation(key=key, route=route, method="POST")
        raise


@teams_bp.route("/api/teams", methods=["POST"])
def teams_create():
    body, status = _idempotent_create(route="/api/teams", create_fn=create_team)
    return jsonify(body), status


@teams_bp.route("/api/teams", methods=["GET"])
def teams_list_route():
    return jsonify([to_api_doc(d) for d in list_teams()]), 200


@teams_bp.route("/api/teams/<team_id>", methods=["GET"])
def teams_get_route(team_id: str):
    oid = parse_required_object_id(team_id, "team id")
    doc = to_api_doc(get_team(oid))
    if not doc:
        raise APIError(404, "team not found")
    return jsonify(doc), 200


@teams_bp.route("/api/teams/<team_id>", methods=["PATCH"])
def teams_patch_route(team_id: str):
    oid = parse_required_object_id(team_id, "team id")
    updated = update_team(oid, json_payload())
    return jsonify(to_api_doc(updated)), 200


@teams_bp.route("/api/teams/<team_id>", methods=["DELETE"])
@require_admin_session
def teams_delete_route(team_id: str):
    oid = parse_required_object_id(team_id, "team id")
    prune_users = request.args.get("pruneUsers", "false").lower() in {"1", "true", "yes"}
    delete_team(oid, prune_users=prune_users)
    return "", 204
