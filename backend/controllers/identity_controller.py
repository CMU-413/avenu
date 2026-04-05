from __future__ import annotations

from flask import Blueprint, jsonify, session

from controllers.common import json_payload
from errors import APIError
from metrics_autologin import autologin_failed_total, autologin_success_total
from repositories import to_api_doc
from services.identity_sync_service import sync_optix_identity

identity_bp = Blueprint("identity", __name__)


@identity_bp.route("/api/optix-token", methods=["POST"])
def optix_token_route():
    payload = json_payload()
    token = payload.get("token")
    if not token:
        autologin_failed_total.inc()
        raise APIError(400, "Missing token")

    try:
        created, user_doc = sync_optix_identity(token=token)
        session["user_id"] = str(user_doc["_id"])
    except Exception:
        autologin_failed_total.inc()
        raise

    autologin_success_total.inc()
    return jsonify({"created": created, "user": to_api_doc(user_doc)}), (201 if created else 200)
