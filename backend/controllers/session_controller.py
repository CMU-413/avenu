from __future__ import annotations

from flask import Blueprint, jsonify, session

from controllers.auth_guard import ensure_session_user
from controllers.common import json_payload
from errors import APIError
from services.user_service import find_user_by_email
from validators import normalize_email, require_string

session_bp = Blueprint("session", __name__)


@session_bp.route("/api/session/login", methods=["POST"])
def session_login():
    payload = json_payload()
    email = normalize_email(require_string(payload, "email", max_len=320))
    user = find_user_by_email(email)
    if user is None:
        raise APIError(401, "unauthorized")
    session["user_id"] = str(user["_id"])
    return "", 204


@session_bp.route("/api/session/logout", methods=["POST"])
def session_logout():
    session.pop("user_id", None)
    return "", 204


@session_bp.route("/api/session/me", methods=["GET"])
def session_me():
    user = ensure_session_user()
    return (
        jsonify(
            {
                "id": str(user["_id"]),
                "email": user.get("email", ""),
                "fullname": user.get("fullname", ""),
                "isAdmin": user.get("isAdmin", False),
                "teamIds": [str(tid) for tid in user.get("teamIds", [])],
                "emailNotifications": "email" in list(user.get("notifPrefs", [])),
            }
        ),
        200,
    )
