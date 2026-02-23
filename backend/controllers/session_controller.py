from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, session

from controllers.auth_guard import ensure_session_user
from controllers.common import json_payload
from errors import APIError
from services.user_preferences import normalize_effective_notification_state
from services.user_service import find_user_by_email
from validators import normalize_email, require_string

session_bp = Blueprint("session", __name__)

_SESSION_EXPIRES_AT_PAST = "Thu, 01 Jan 1970 00:00:00 GMT"


def _build_session_cookie_delete_header(*, secure: bool, partitioned: bool) -> str:
    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
    cookie_path = current_app.config.get("SESSION_COOKIE_PATH", "/")
    cookie_domain = current_app.config.get("SESSION_COOKIE_DOMAIN")
    cookie_samesite = current_app.config.get("SESSION_COOKIE_SAMESITE")

    parts = [
        f"{cookie_name}=",
        f"Expires={_SESSION_EXPIRES_AT_PAST}",
        "Max-Age=0",
        f"Path={cookie_path}",
        "HttpOnly",
    ]
    if cookie_domain:
        parts.append(f"Domain={cookie_domain}")
    if secure:
        parts.append("Secure")
    if cookie_samesite:
        parts.append(f"SameSite={cookie_samesite}")
    if partitioned:
        parts.append("Partitioned")
    return "; ".join(parts)


def _clear_session_cookie_variants(response) -> None:
    # Delete both modern and legacy variants so old cookies cannot revive sessions.
    variants = (
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    )
    for secure, partitioned in variants:
        response.headers.add(
            "Set-Cookie",
            _build_session_cookie_delete_header(secure=secure, partitioned=partitioned),
        )


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
    session.clear()
    response = make_response("", 204)
    _clear_session_cookie_variants(response)
    return response


@session_bp.route("/api/session/me", methods=["GET"])
def session_me():
    user = ensure_session_user()
    normalized = normalize_effective_notification_state(current_user=user)
    return (
        jsonify(
            {
                "id": str(user["_id"]),
                "email": user.get("email", ""),
                "fullname": user.get("fullname", ""),
                "isAdmin": user.get("isAdmin", False),
                "teamIds": [str(tid) for tid in user.get("teamIds", [])],
                "emailNotifications": normalized["emailNotifications"],
                "smsNotifications": normalized["smsNotifications"],
                "hasPhone": normalized["hasPhone"],
            }
        ),
        200,
    )
