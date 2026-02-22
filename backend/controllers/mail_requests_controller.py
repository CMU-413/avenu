from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from controllers.auth_guard import ensure_member_session, ensure_session_user, require_admin_session
from controllers.common import json_payload, parse_optional_object_id_filter, parse_required_object_id
from errors import APIError
from repositories import to_api_doc
from services.mail_request_service import (
    cancel_member_mail_request,
    create_mail_request,
    list_admin_active_mail_requests,
    list_member_mail_requests,
    resolve_mail_request_and_notify,
    retry_mail_request_notification,
)
from services.notifications.channels.factory import build_notification_channels
from services.notifications.special_case_notifier import SpecialCaseNotifier

mail_requests_bp = Blueprint("mail_requests", __name__)


@mail_requests_bp.route("/api/mail-requests", methods=["POST"])
def member_mail_requests_create_route():
    user = ensure_member_session()
    created = create_mail_request(user=user, payload=json_payload())
    return jsonify(to_api_doc(created)), 201


@mail_requests_bp.route("/api/mail-requests", methods=["GET"])
def member_mail_requests_list_route():
    user = ensure_member_session()
    status_filter = (request.args.get("status") or "ACTIVE").strip().upper()
    if status_filter not in {"ACTIVE", "RESOLVED", "ALL"}:
        raise APIError(422, "status must be one of ACTIVE, RESOLVED, ALL")
    return jsonify([to_api_doc(doc) for doc in list_member_mail_requests(user=user, status_filter=status_filter)]), 200


@mail_requests_bp.route("/api/mail-requests/<request_id>", methods=["DELETE"])
def member_mail_requests_cancel_route(request_id: str):
    user = ensure_member_session()
    oid = parse_required_object_id(request_id, "mail request id")
    cancel_member_mail_request(user=user, request_id=oid)
    return "", 204


@mail_requests_bp.route("/api/admin/mail-requests", methods=["GET"])
@require_admin_session
def admin_mail_requests_list_route():
    mailbox_id = parse_optional_object_id_filter(request.args.get("mailboxId"), field_name="mailboxId")
    member_id = parse_optional_object_id_filter(request.args.get("memberId"), field_name="memberId")
    return jsonify(
        [to_api_doc(doc) for doc in list_admin_active_mail_requests(mailbox_id=mailbox_id, member_id=member_id)]
    ), 200


@mail_requests_bp.route("/api/admin/mail-requests/<request_id>/resolve", methods=["POST"])
@require_admin_session
def admin_mail_requests_resolve_route(request_id: str):
    admin_user = ensure_session_user()
    oid = parse_required_object_id(request_id, "mail request id")
    notifier = SpecialCaseNotifier(
        channels=build_notification_channels(testing=current_app.config.get("TESTING", False))
    )
    updated = resolve_mail_request_and_notify(request_id=oid, admin_user=admin_user, notifier=notifier)
    return jsonify(to_api_doc(updated)), 200


@mail_requests_bp.route("/api/admin/mail-requests/<request_id>/retry-notification", methods=["POST"])
@require_admin_session
def admin_mail_requests_retry_notification_route(request_id: str):
    admin_user = ensure_session_user()
    oid = parse_required_object_id(request_id, "mail request id")
    notifier = SpecialCaseNotifier(
        channels=build_notification_channels(testing=current_app.config.get("TESTING", False))
    )
    updated = retry_mail_request_notification(request_id=oid, admin_user=admin_user, notifier=notifier)
    return jsonify(to_api_doc(updated)), 200
