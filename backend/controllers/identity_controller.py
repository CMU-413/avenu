from __future__ import annotations

from flask import Blueprint, jsonify, session

from controllers.common import json_payload
from errors import APIError
from repositories import to_api_doc
from services.identity_sync_service import sync_optix_identity

identity_bp = Blueprint("identity", __name__)


@identity_bp.route("/api/optix-token", methods=["POST"])
def optix_token_route():
    payload = json_payload()
    token = payload.get("token")
    if not token:
        raise APIError(400, "Missing token")

    created, user_doc = sync_optix_identity(token=token)
    session["user_id"] = str(user_doc["_id"])
    return jsonify({"created": created, "user": to_api_doc(user_doc)}), (201 if created else 200)
