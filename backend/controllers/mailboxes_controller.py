from __future__ import annotations

from flask import Blueprint, jsonify

from controllers.auth_guard import require_admin_session
from controllers.common import json_payload, parse_required_object_id
from errors import APIError
from repositories import to_api_doc
from services.mailbox_service import get_mailbox, list_mailboxes, update_mailbox

mailboxes_bp = Blueprint("mailboxes", __name__)


@mailboxes_bp.route("/api/mailboxes", methods=["GET"])
@require_admin_session
def mailboxes_list_route():
    return jsonify([to_api_doc(d) for d in list_mailboxes()]), 200


@mailboxes_bp.route("/api/mailboxes/<mailbox_id>", methods=["GET"])
@require_admin_session
def mailboxes_get_route(mailbox_id: str):
    oid = parse_required_object_id(mailbox_id, "mailbox id")
    doc = to_api_doc(get_mailbox(oid))
    if not doc:
        raise APIError(404, "mailbox not found")
    return jsonify(doc), 200


@mailboxes_bp.route("/api/mailboxes/<mailbox_id>", methods=["PATCH"])
@require_admin_session
def mailboxes_patch_route(mailbox_id: str):
    oid = parse_required_object_id(mailbox_id, "mailbox id")
    updated = update_mailbox(oid, json_payload())
    return jsonify(to_api_doc(updated)), 200
