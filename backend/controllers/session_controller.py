from __future__ import annotations

import math

from flask import Blueprint, current_app, jsonify, make_response, render_template, session

from controllers.auth_guard import ensure_session_user
from controllers.common import json_payload
from errors import APIError
from services.auth_magic_link_service import AuthMagicLinkService
from services.notifications.providers.email_provider import MailProviderError
from services.notifications.providers.factory import build_email_provider
from services.user_preferences import normalize_effective_notification_state
from services.user_service import find_user_by_email, get_user
from validators import normalize_email, require_string

session_bp = Blueprint("session", __name__)

_SESSION_EXPIRES_AT_PAST = "Thu, 01 Jan 1970 00:00:00 GMT"
_MAGIC_LINK_EMAIL_SUBJECT = "Your Avenu admin sign-in link"


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
    if user is None or user.get("isAdmin") is not True:
        return jsonify({"status": "ok"}), 202

    auth_magic_links = AuthMagicLinkService()
    magic_link = auth_magic_links.generate_admin_login_link(user=user)
    expiry_minutes = max(1, math.ceil(auth_magic_links.link_expiry_seconds / 60))

    try:
        email_provider = build_email_provider(testing=bool(current_app.config.get("TESTING")))
        email_provider.send(
            to=email,
            subject=_MAGIC_LINK_EMAIL_SUBJECT,
            html=render_template(
                "emails/admin_magic_link.html",
                user=user,
                magic_link=magic_link,
                expiry_minutes=expiry_minutes,
            ),
        )
    except MailProviderError as exc:
        raise APIError(503, "unable to send sign-in email") from exc

    return jsonify({"status": "ok"}), 202


@session_bp.route("/api/session/redeem", methods=["POST"])
def session_redeem():
    payload = json_payload()
    token_id = require_string(payload, "tokenId", max_len=512)
    signature = require_string(payload, "signature", max_len=4096)
    verified = AuthMagicLinkService().verify_login_link(token_id=token_id, signature=signature)
    user = get_user(verified["userId"])
    if user is None or user.get("isAdmin") is not True:
        raise APIError(401, "unauthorized")
    session["user_id"] = str(verified["userId"])
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
