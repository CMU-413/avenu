from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request

from controllers.auth_guard import require_admin_session
from controllers.common import json_payload, parse_required_object_id
from errors import APIError
from idempotency import payload_hash, require_idempotency_key
from repositories import to_api_doc
from repositories.idempotency_repository import delete_reservation, reserve_or_replay_request, store_response
from services.user_service import create_user, delete_user, get_user, list_users, update_user

users_bp = Blueprint("users", __name__)


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


@users_bp.route("/api/users", methods=["POST"])
def users_create():
    body, status = _idempotent_create(route="/api/users", create_fn=create_user)
    return jsonify(body), status


@users_bp.route("/api/users", methods=["GET"])
@require_admin_session
def users_list_route():
    return jsonify([to_api_doc(d) for d in list_users()]), 200


@users_bp.route("/api/users/<user_id>", methods=["GET"])
def users_get(user_id: str):
    oid = parse_required_object_id(user_id, "user id")
    doc = to_api_doc(get_user(oid))
    if not doc:
        raise APIError(404, "user not found")
    return jsonify(doc), 200


@users_bp.route("/api/users/<user_id>", methods=["PATCH"])
@require_admin_session
def users_patch(user_id: str):
    oid = parse_required_object_id(user_id, "user id")
    updated = update_user(oid, json_payload())
    return jsonify(to_api_doc(updated)), 200


@users_bp.route("/api/users/<user_id>", methods=["DELETE"])
@require_admin_session
def users_delete(user_id: str):
    oid = parse_required_object_id(user_id, "user id")
    delete_user(oid)
    return "", 204
