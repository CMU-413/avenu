from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from flask import Flask, jsonify, request, session

from auth import ensure_admin_session, ensure_member_session, ensure_session_user, require_admin_session
from config import SECRET_KEY, SESSION_COOKIE_SECURE, ensure_indexes, idempotency_keys_collection
from errors import APIError
from idempotency import payload_hash, require_idempotency_key, reserve_or_replay, store_idempotent_response
from repositories import to_api_doc
from services.mail_service import create_mail, delete_mail, get_mail, list_mail, update_mail
from services.mailbox_service import get_mailbox, list_mailboxes, update_mailbox
from services.member_service import list_member_mail_summary, update_member_email_notifications
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.special_case_notifier import SpecialCaseNotifier
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier
from services.team_service import create_team, delete_team, get_team, list_teams, update_team
from services.user_service import (
    create_user,
    delete_user,
    find_user_by_email,
    get_user,
    list_users,
    update_user,
)
from validators import normalize_email, parse_object_id, require_dict, require_string


def _json_payload() -> dict[str, Any]:
    return require_dict(request.get_json(silent=True))


def _parse_day_utc(date_value: str) -> tuple[datetime, datetime]:
    try:
        day = datetime.strptime(date_value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise APIError(422, "date must be YYYY-MM-DD") from exc
    return day, day + timedelta(days=1)


def _parse_iso_date(value: str, *, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise APIError(422, f"{field_name} must be YYYY-MM-DD") from exc


def _idempotent_create(
    *,
    route: str,
    create_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    payload = _json_payload()
    key = require_idempotency_key(request.headers)
    request_hash = payload_hash(payload)

    replay = reserve_or_replay(
        idempotency_keys_collection,
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
        store_idempotent_response(
            idempotency_keys_collection,
            key=key,
            route=route,
            method="POST",
            status=201,
            body=body,
        )
        return body, 201
    except Exception:
        idempotency_keys_collection.delete_one({"key": key, "route": route, "method": "POST"})
        raise


def create_app(
    *,
    testing: bool = False,
    ensure_db_indexes_on_startup: bool = True,
    secret_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing

    resolved_secret_key = SECRET_KEY if secret_key is None else secret_key

    if not testing and not resolved_secret_key:
        raise RuntimeError("SECRET_KEY must be set")

    app.config["SECRET_KEY"] = resolved_secret_key or "test-secret-key"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False if testing else SESSION_COOKIE_SECURE

    if ensure_db_indexes_on_startup and not testing:
        ensure_indexes()

    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return jsonify({"error": err.message}), err.status_code

    @app.errorhandler(500)
    def handle_unexpected(_err):
        return jsonify({"error": "internal server error"}), 500

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"message": "HEALTH OK"}), 200

    @app.route("/api/session/login", methods=["POST"])
    def session_login():
        payload = _json_payload()
        email = normalize_email(require_string(payload, "email", max_len=320))
        user = find_user_by_email(email)
        if user is None:
            raise APIError(401, "unauthorized")
        session["user_id"] = str(user["_id"])
        return "", 204

    @app.route("/api/session/logout", methods=["POST"])
    def session_logout():
        session.pop("user_id", None)
        return "", 204

    @app.route("/api/session/me", methods=["GET"])
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

    @app.route("/api/users", methods=["POST"])
    def users_create():
        body, status = _idempotent_create(route="/api/users", create_fn=create_user)
        return jsonify(body), status

    @app.route("/api/users", methods=["GET"])
    @require_admin_session
    def users_list():
        return jsonify([to_api_doc(d) for d in list_users()]), 200

    @app.route("/api/users/<user_id>", methods=["GET"])
    def users_get(user_id: str):
        oid = parse_object_id(user_id, "user id")
        doc = to_api_doc(get_user(oid))
        if not doc:
            raise APIError(404, "user not found")
        return jsonify(doc), 200

    @app.route("/api/users/<user_id>", methods=["PATCH"])
    @require_admin_session
    def users_patch(user_id: str):
        oid = parse_object_id(user_id, "user id")
        updated = update_user(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/users/<user_id>", methods=["DELETE"])
    @require_admin_session
    def users_delete(user_id: str):
        oid = parse_object_id(user_id, "user id")
        delete_user(oid)
        return "", 204

    @app.route("/api/teams", methods=["POST"])
    def teams_create():
        body, status = _idempotent_create(route="/api/teams", create_fn=create_team)
        return jsonify(body), status

    @app.route("/api/teams", methods=["GET"])
    def teams_list_route():
        return jsonify([to_api_doc(d) for d in list_teams()]), 200

    @app.route("/api/teams/<team_id>", methods=["GET"])
    def teams_get_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        doc = to_api_doc(get_team(oid))
        if not doc:
            raise APIError(404, "team not found")
        return jsonify(doc), 200

    @app.route("/api/teams/<team_id>", methods=["PATCH"])
    def teams_patch_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        updated = update_team(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/teams/<team_id>", methods=["DELETE"])
    def teams_delete_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        prune_users = request.args.get("pruneUsers", "false").lower() in {"1", "true", "yes"}
        if prune_users:
            ensure_admin_session()
        delete_team(oid, prune_users=prune_users)
        return "", 204

    @app.route("/api/mailboxes", methods=["GET"])
    @require_admin_session
    def mailboxes_list_route():
        return jsonify([to_api_doc(d) for d in list_mailboxes()]), 200

    @app.route("/api/mailboxes/<mailbox_id>", methods=["GET"])
    @require_admin_session
    def mailboxes_get_route(mailbox_id: str):
        oid = parse_object_id(mailbox_id, "mailbox id")
        doc = to_api_doc(get_mailbox(oid))
        if not doc:
            raise APIError(404, "mailbox not found")
        return jsonify(doc), 200

    @app.route("/api/mailboxes/<mailbox_id>", methods=["PATCH"])
    @require_admin_session
    def mailboxes_patch_route(mailbox_id: str):
        oid = parse_object_id(mailbox_id, "mailbox id")
        updated = update_mailbox(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/mail", methods=["POST"])
    @require_admin_session
    def mail_create_route():
        body, status = _idempotent_create(route="/api/mail", create_fn=create_mail)
        return jsonify(body), status

    @app.route("/api/mail", methods=["GET"])
    @require_admin_session
    def mail_list_route():
        date_value = request.args.get("date")
        mailbox_id_value = request.args.get("mailboxId")
        day_start = None
        day_end = None
        if date_value is not None:
            day_start, day_end = _parse_day_utc(date_value)
        mailbox_id = parse_object_id(mailbox_id_value, "mailbox id") if mailbox_id_value else None
        return jsonify([to_api_doc(d) for d in list_mail(day_start=day_start, day_end=day_end, mailbox_id=mailbox_id)]), 200

    @app.route("/api/mail/<mail_id>", methods=["GET"])
    @require_admin_session
    def mail_get_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        doc = to_api_doc(get_mail(oid))
        if not doc:
            raise APIError(404, "mail not found")
        return jsonify(doc), 200

    @app.route("/api/mail/<mail_id>", methods=["PATCH"])
    @require_admin_session
    def mail_patch_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        updated = update_mail(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/mail/<mail_id>", methods=["DELETE"])
    @require_admin_session
    def mail_delete_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        delete_mail(oid)
        return "", 204

    @app.route("/api/member/mail", methods=["GET"])
    def member_mail_route():
        user = ensure_member_session()
        start_value = request.args.get("start")
        end_value = request.args.get("end")
        if start_value is None or end_value is None:
            raise APIError(422, "start and end are required")
        start_day = _parse_iso_date(start_value, field_name="start")
        end_day = _parse_iso_date(end_value, field_name="end")
        if end_day < start_day:
            raise APIError(422, "end must be on or after start")
        return jsonify(list_member_mail_summary(user=user, start_day=start_day, end_day=end_day)), 200

    @app.route("/api/member/preferences", methods=["PATCH"])
    def member_preferences_route():
        user = ensure_member_session()
        payload = _json_payload()
        email_notifications = payload.get("emailNotifications")
        if not isinstance(email_notifications, bool):
            raise APIError(422, "emailNotifications must be a boolean")
        return jsonify(update_member_email_notifications(user=user, enabled=email_notifications)), 200

    @app.route("/api/admin/notifications/summary", methods=["POST"])
    @app.route("/admin/notifications/summary", methods=["POST"])
    @require_admin_session
    def admin_weekly_summary_route():
        payload = _json_payload()
        user_id = parse_object_id(require_string(payload, "userId"), "user id")
        week_start = _parse_iso_date(require_string(payload, "weekStart"), field_name="weekStart")
        week_end = _parse_iso_date(require_string(payload, "weekEnd"), field_name="weekEnd")
        if week_end < week_start:
            raise APIError(422, "weekEnd must be on or after weekStart")

        notifier = WeeklySummaryNotifier(channels=[EmailChannel(ConsoleEmailProvider())])
        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=week_start,
            weekEnd=week_end,
            triggeredBy="admin",
        )
        return jsonify(result), 200

    @app.route("/api/admin/notifications/special", methods=["POST"])
    @app.route("/admin/notifications/special", methods=["POST"])
    @require_admin_session
    def admin_special_notification_route():
        payload = _json_payload()
        user_id = parse_object_id(require_string(payload, "userId"), "user id")

        notifier = SpecialCaseNotifier(channels=[EmailChannel(ConsoleEmailProvider())])
        result = notifier.notifySpecialCase(
            userId=user_id,
            triggeredBy="admin",
        )
        return jsonify(result), 200

    return app


app = create_app(testing=os.getenv("FLASK_TESTING", "").strip().lower() in {"1", "true", "yes"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
