from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from controllers.auth_guard import require_admin_session
from controllers.common import json_payload, parse_iso_date, parse_required_object_id
from errors import APIError
from services.notifications.channels.factory import build_notification_channels
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier
from validators import require_string

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/api/admin/notifications/summary", methods=["POST"])
@notifications_bp.route("/admin/notifications/summary", methods=["POST"])
@require_admin_session
def admin_weekly_summary_route():
    payload = json_payload()
    user_id = parse_required_object_id(require_string(payload, "userId"), "user id")
    week_start = parse_iso_date(require_string(payload, "weekStart"), field_name="weekStart")
    week_end = parse_iso_date(require_string(payload, "weekEnd"), field_name="weekEnd")
    if week_end < week_start:
        raise APIError(422, "weekEnd must be on or after weekStart")

    notifier = WeeklySummaryNotifier(
        channels=build_notification_channels(testing=current_app.config.get("TESTING", False))
    )
    result = notifier.notifyWeeklySummary(
        userId=user_id,
        weekStart=week_start,
        weekEnd=week_end,
        triggeredBy="admin",
    )
    return jsonify(result), 200
