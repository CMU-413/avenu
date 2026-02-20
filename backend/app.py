from __future__ import annotations

import hmac
import os
from datetime import date, datetime
from typing import Any

import requests
from bson import ObjectId
from flask import Flask, jsonify, request, session

from config import (
    FRONTEND_ORIGINS,
    SCHEDULER_INTERNAL_TOKEN,
    SECRET_KEY,
    SESSION_COOKIE_PARTITIONED,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    ensure_indexes,
    idempotency_keys_collection,
)
from controllers import register_phase1_blueprints
from controllers.auth_guard import ensure_admin_session, ensure_member_session, ensure_session_user, require_admin_session
from controllers.common import json_payload, parse_iso_date, parse_optional_object_id_filter
from errors import APIError
from idempotency import payload_hash, require_idempotency_key, reserve_or_replay, store_idempotent_response
from repositories import to_api_doc
from repositories.teams_repository import find_team_by_optix_id
from repositories.users_repository import find_user_by_optix_id
from services.mail_request_service import (
    cancel_member_mail_request,
    create_mail_request,
    list_admin_active_mail_requests,
    list_member_mail_requests,
    resolve_mail_request_and_notify,
    retry_mail_request_notification,
)
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.providers.factory import build_email_provider
from services.notifications.special_case_notifier import SpecialCaseNotifier
from services.notifications.weekly_summary_cron_job import run_weekly_summary_cron_job
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier
from services.team_service import create_team
from services.user_service import create_user, update_user
from validators import parse_object_id, require_dict, require_string


def _require_scheduler_token() -> None:
    provided = (request.headers.get("X-Scheduler-Token") or "").strip()
    if not SCHEDULER_INTERNAL_TOKEN:
        raise APIError(503, "scheduler token is not configured")
    if not provided or not hmac.compare_digest(provided, SCHEDULER_INTERNAL_TOKEN):
        raise APIError(401, "unauthorized")


def _weekly_job_response_body(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "weekStart": result["weekStart"].isoformat(),
        "weekEnd": result["weekEnd"].isoformat(),
        "processed": result["processed"],
        "sent": result["sent"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "errors": result["errors"],
    }


def create_app(
    *,
    testing: bool = False,
    ensure_db_indexes_on_startup: bool = True,
    secret_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing
    resolved_frontend_origins = tuple(FRONTEND_ORIGINS)

    resolved_secret_key = SECRET_KEY if secret_key is None else secret_key

    if not testing and not resolved_secret_key:
        raise RuntimeError("SECRET_KEY must be set")
    if not testing and "*" in resolved_frontend_origins:
        raise RuntimeError("FRONTEND_ORIGINS cannot include wildcard '*' in non-testing mode")
    if not testing and not SCHEDULER_INTERNAL_TOKEN:
        raise RuntimeError("SCHEDULER_INTERNAL_TOKEN must be set")

    app.config["SECRET_KEY"] = resolved_secret_key or "test-secret-key"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"] = False if testing else SESSION_COOKIE_SECURE
    app.config["SESSION_COOKIE_PARTITIONED"] = False if testing else SESSION_COOKIE_PARTITIONED

    if not testing and SESSION_COOKIE_SAMESITE == "None" and not SESSION_COOKIE_SECURE:
        raise RuntimeError("SESSION_COOKIE_SAMESITE=None requires SESSION_COOKIE_SECURE=true")

    if ensure_db_indexes_on_startup and not testing:
        ensure_indexes()

    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return jsonify({"error": err.message}), err.status_code

    @app.errorhandler(500)
    def handle_unexpected(_err):
        return jsonify({"error": "internal server error"}), 500

    @app.after_request
    def apply_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin in resolved_frontend_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Idempotency-Key, X-Scheduler-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            existing_vary = response.headers.get("Vary")
            response.headers["Vary"] = "Origin" if not existing_vary else f"{existing_vary}, Origin"
        return response

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"message": "HEALTH OK"}), 200

    register_phase1_blueprints(app)

    @app.route("/api/internal/jobs/weekly-summary", methods=["POST"])
    def internal_weekly_summary_job_route():
        _require_scheduler_token()

        body_raw = request.get_json(silent=True)
        payload = {} if body_raw is None else require_dict(body_raw)
        week_start_value = payload.get("weekStart")
        week_end_value = payload.get("weekEnd")
        week_start = None
        week_end = None

        if (week_start_value is None) != (week_end_value is None):
            raise APIError(422, "weekStart and weekEnd must be provided together")
        if week_start_value is not None:
            if not isinstance(week_start_value, str):
                raise APIError(422, "weekStart must be YYYY-MM-DD")
            if not isinstance(week_end_value, str):
                raise APIError(422, "weekEnd must be YYYY-MM-DD")
            week_start = parse_iso_date(week_start_value, field_name="weekStart")
            week_end = parse_iso_date(week_end_value, field_name="weekEnd")
            if week_end < week_start:
                raise APIError(422, "weekEnd must be on or after weekStart")

        idempotency_key = require_idempotency_key(request.headers)
        request_hash = payload_hash(payload)
        route = "/api/internal/jobs/weekly-summary"
        replay = reserve_or_replay(
            idempotency_keys_collection,
            key=idempotency_key,
            route=route,
            method="POST",
            request_hash=request_hash,
        )
        if replay is not None:
            return jsonify(replay["body"]), replay["status"]

        try:
            notifier = WeeklySummaryNotifier(channels=[EmailChannel(build_email_provider(testing=testing))])
            result = run_weekly_summary_cron_job(
                notifier=notifier,
                week_start=week_start,
                week_end=week_end,
            )
            body = _weekly_job_response_body(result)
            store_idempotent_response(
                idempotency_keys_collection,
                key=idempotency_key,
                route=route,
                method="POST",
                status=200,
                body=body,
            )
            return jsonify(body), 200
        except Exception:
            idempotency_keys_collection.delete_one({"key": idempotency_key, "route": route, "method": "POST"})
            raise

    @app.route("/api/mail-requests", methods=["POST"])
    def member_mail_requests_create_route():
        user = ensure_member_session()
        created = create_mail_request(user=user, payload=json_payload())
        return jsonify(to_api_doc(created)), 201

    @app.route("/api/mail-requests", methods=["GET"])
    def member_mail_requests_list_route():
        user = ensure_member_session()
        status_filter = (request.args.get("status") or "ACTIVE").strip().upper()
        if status_filter not in {"ACTIVE", "RESOLVED", "ALL"}:
            raise APIError(422, "status must be one of ACTIVE, RESOLVED, ALL")
        return jsonify([to_api_doc(doc) for doc in list_member_mail_requests(user=user, status_filter=status_filter)]), 200

    @app.route("/api/mail-requests/<request_id>", methods=["DELETE"])
    def member_mail_requests_cancel_route(request_id: str):
        user = ensure_member_session()
        oid = ObjectId(request_id) if ObjectId.is_valid(request_id) else None
        if oid is None:
            raise APIError(422, "mail request id must be a valid ObjectId string")
        cancel_member_mail_request(user=user, request_id=oid)
        return "", 204

    @app.route("/api/admin/mail-requests", methods=["GET"])
    @require_admin_session
    def admin_mail_requests_list_route():
        mailbox_id = parse_optional_object_id_filter(request.args.get("mailboxId"), field_name="mailboxId")
        member_id = parse_optional_object_id_filter(request.args.get("memberId"), field_name="memberId")
        return jsonify(
            [to_api_doc(doc) for doc in list_admin_active_mail_requests(mailbox_id=mailbox_id, member_id=member_id)]
        ), 200

    @app.route("/api/admin/mail-requests/<request_id>/resolve", methods=["POST"])
    @require_admin_session
    def admin_mail_requests_resolve_route(request_id: str):
        admin_user = ensure_session_user()
        oid = ObjectId(request_id) if ObjectId.is_valid(request_id) else None
        if oid is None:
            raise APIError(422, "mail request id must be a valid ObjectId string")
        notifier = SpecialCaseNotifier(channels=[EmailChannel(build_email_provider(testing=testing))])
        updated = resolve_mail_request_and_notify(request_id=oid, admin_user=admin_user, notifier=notifier)
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/admin/mail-requests/<request_id>/retry-notification", methods=["POST"])
    @require_admin_session
    def admin_mail_requests_retry_notification_route(request_id: str):
        admin_user = ensure_session_user()
        oid = ObjectId(request_id) if ObjectId.is_valid(request_id) else None
        if oid is None:
            raise APIError(422, "mail request id must be a valid ObjectId string")
        notifier = SpecialCaseNotifier(channels=[EmailChannel(build_email_provider(testing=testing))])
        updated = retry_mail_request_notification(request_id=oid, admin_user=admin_user, notifier=notifier)
        return jsonify(to_api_doc(updated)), 200

    @app.route("/api/admin/notifications/summary", methods=["POST"])
    @app.route("/admin/notifications/summary", methods=["POST"])
    @require_admin_session
    def admin_weekly_summary_route():
        payload = json_payload()
        user_id = parse_object_id(require_string(payload, "userId"), "user id")
        week_start = parse_iso_date(require_string(payload, "weekStart"), field_name="weekStart")
        week_end = parse_iso_date(require_string(payload, "weekEnd"), field_name="weekEnd")
        if week_end < week_start:
            raise APIError(422, "weekEnd must be on or after weekStart")

        notifier = WeeklySummaryNotifier(channels=[EmailChannel(build_email_provider(testing=testing))])
        result = notifier.notifyWeeklySummary(
            userId=user_id,
            weekStart=week_start,
            weekEnd=week_end,
            triggeredBy="admin",
        )
        return jsonify(result), 200

    return app


app = create_app(testing=os.getenv("FLASK_TESTING", "").strip().lower() in {"1", "true", "yes"})


def _coerce_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise APIError(422, f"{field_name} must be a positive integer")
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            value = int(value)
    if not isinstance(value, int) or value < 1:
        raise APIError(422, f"{field_name} must be a positive integer")
    return value


@app.route("/api/optix-token", methods=["POST"])
def optix_token_route():
    payload = json_payload()
    token = payload.get("token")
    if not token:
        raise APIError(400, "Missing token")

    resp = requests.post(
        "https://api.optixapp.com/graphql",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json={
            "query": """
            query {
              me {
                user {
                  user_id
                  email
                  name
                  is_admin
                  teams {
                    team_id
                    name
                  }
                }
              }
            }
            """,
        },
    )

    if resp.status_code != 200:
        return jsonify({"error": "Failed to query Optix API", "status": resp.status_code}), resp.status_code

    data = resp.json()
    user_info = data.get("data", {}).get("me", {}).get("user", {})
    if not user_info:
        return jsonify({"error": "No user info returned from Optix"}), 400

    optix_user_id = _coerce_positive_int(user_info.get("user_id"), field_name="user_id")
    existing_user = find_user_by_optix_id(optix_user_id)

    team_ids = []
    for team in user_info.get("teams", []):
        optix_team_id = _coerce_positive_int(team.get("team_id"), field_name="team_id")
        team_doc = find_team_by_optix_id(optix_team_id)
        if not team_doc:
            team_doc = create_team({"optixId": optix_team_id, "name": team.get("name", "")})
        team_ids.append(team_doc["_id"])

    user_payload = {
        "optixId": optix_user_id,
        "fullname": user_info.get("name", ""),
        "email": user_info.get("email", ""),
        "isAdmin": user_info.get("is_admin", False),
        "teamIds": team_ids,
        "notifPrefs": ["email"],
    }

    if not existing_user:
        user_doc = create_user(user_payload)
        session["user_id"] = str(user_doc["_id"])
        return jsonify({"created": True, "user": to_api_doc(user_doc)}), 201

    user_id = existing_user["_id"]
    update_user(user_id, user_payload)
    updated_user = find_user_by_optix_id(optix_user_id)
    if not updated_user:
        raise APIError(500, "failed to fetch updated user")
    session["user_id"] = str(updated_user["_id"])
    return jsonify({"created": False, "user": to_api_doc(updated_user)}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
