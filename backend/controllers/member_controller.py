from __future__ import annotations

from flask import Blueprint, jsonify, request

from controllers.auth_guard import ensure_member_session
from controllers.common import json_payload, parse_iso_date
from errors import APIError
from services.member_service import list_member_mail_summary, update_member_email_notifications

member_bp = Blueprint("member", __name__)


@member_bp.route("/api/member/mail", methods=["GET"])
def member_mail_route():
    user = ensure_member_session()
    start_value = request.args.get("start")
    end_value = request.args.get("end")
    if start_value is None or end_value is None:
        raise APIError(422, "start and end are required")
    start_day = parse_iso_date(start_value, field_name="start")
    end_day = parse_iso_date(end_value, field_name="end")
    if end_day < start_day:
        raise APIError(422, "end must be on or after start")
    return jsonify(list_member_mail_summary(user=user, start_day=start_day, end_day=end_day)), 200


@member_bp.route("/api/member/preferences", methods=["PATCH"])
def member_preferences_route():
    user = ensure_member_session()
    payload = json_payload()
    email_notifications = payload.get("emailNotifications")
    if not isinstance(email_notifications, bool):
        raise APIError(422, "emailNotifications must be a boolean")
    return jsonify(update_member_email_notifications(user=user, enabled=email_notifications)), 200
