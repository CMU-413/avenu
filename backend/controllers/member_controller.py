from __future__ import annotations

from flask import Blueprint, jsonify, request

from controllers.auth_guard import ensure_member_session
from controllers.common import json_payload, parse_iso_date
from errors import APIError
from metrics.metrics_dashboard import member_dashboard_views_total
from services.member_service import list_member_mail_summary, update_member_notification_preferences
from services.user_preferences import UNSET

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
    payload = list_member_mail_summary(user=user, start_day=start_day, end_day=end_day)
    member_dashboard_views_total.inc()
    return jsonify(payload), 200


@member_bp.route("/api/member/preferences", methods=["PATCH"])
def member_preferences_route():
    user = ensure_member_session()
    payload = json_payload()
    has_email = "emailNotifications" in payload
    has_sms = "smsNotifications" in payload
    if not has_email and not has_sms:
        raise APIError(400, "no update payload provided")

    email_notifications: bool | object = UNSET
    sms_notifications: bool | object = UNSET
    if has_email:
        email_notifications = payload.get("emailNotifications")
        if not isinstance(email_notifications, bool):
            raise APIError(422, "emailNotifications must be a boolean")
    if has_sms:
        sms_notifications = payload.get("smsNotifications")
        if not isinstance(sms_notifications, bool):
            raise APIError(422, "smsNotifications must be a boolean")

    return (
        jsonify(
            update_member_notification_preferences(
                user=user,
                email_notifications=email_notifications,
                sms_notifications=sms_notifications,
            )
        ),
        200,
    )
