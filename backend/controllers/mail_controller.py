from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request

from controllers.auth_guard import require_admin_session
from controllers.common import json_payload, parse_day_utc, parse_required_object_id
from errors import APIError
from idempotency import payload_hash, require_idempotency_key
from repositories import to_api_doc
from repositories.idempotency_repository import delete_reservation, reserve_or_replay_request, store_response
from services.mail_service import create_mail, delete_mail, get_mail, list_mail, update_mail

mail_bp = Blueprint("mail", __name__)


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


@mail_bp.route("/api/mail", methods=["POST"])
@require_admin_session
def mail_create_route():
    body, status = _idempotent_create(route="/api/mail", create_fn=create_mail)
    return jsonify(body), status


@mail_bp.route("/api/mail", methods=["GET"])
@require_admin_session
def mail_list_route():
    date_value = request.args.get("date")
    mailbox_id_value = request.args.get("mailboxId")
    day_start = None
    day_end = None
    if date_value is not None:
        day_start, day_end = parse_day_utc(date_value)
    mailbox_id = parse_required_object_id(mailbox_id_value, "mailbox id") if mailbox_id_value else None
    return jsonify([to_api_doc(d) for d in list_mail(day_start=day_start, day_end=day_end, mailbox_id=mailbox_id)]), 200


@mail_bp.route("/api/mail/<mail_id>", methods=["GET"])
@require_admin_session
def mail_get_route(mail_id: str):
    oid = parse_required_object_id(mail_id, "mail id")
    doc = to_api_doc(get_mail(oid))
    if not doc:
        raise APIError(404, "mail not found")
    return jsonify(doc), 200


@mail_bp.route("/api/mail/<mail_id>", methods=["PATCH"])
@require_admin_session
def mail_patch_route(mail_id: str):
    oid = parse_required_object_id(mail_id, "mail id")
    updated = update_mail(oid, json_payload())
    return jsonify(to_api_doc(updated)), 200


@mail_bp.route("/api/mail/<mail_id>", methods=["DELETE"])
@require_admin_session
def mail_delete_route(mail_id: str):
    oid = parse_required_object_id(mail_id, "mail id")
    delete_mail(oid)
    return "", 204
