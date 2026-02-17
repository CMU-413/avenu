from __future__ import annotations

from typing import Any, Callable

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import ADMIN_API_KEY, ensure_indexes, idempotency_keys_collection
from errors import APIError
from idempotency import payload_hash, require_idempotency_key, reserve_or_replay, store_idempotent_response
from repositories import to_api_doc
from services.auth import require_admin
from services.mail_service import create_mail, delete_mail, get_mail, list_mail, update_mail
from services.mailbox_service import get_mailbox, list_mailboxes, update_mailbox
from services.team_service import create_team, delete_team, get_team, list_teams, update_team
from services.user_service import create_user, delete_user, get_user, list_users, update_user
from validators import parse_object_id, require_dict

from auth import require_admin as require_admin_api_key


def _json_payload() -> dict[str, Any]:
    return require_dict(request.get_json(silent=True))


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


def create_app() -> Flask:
    app = Flask(__name__)

    CORS(
        app,
        resources={r"/*": {"origins": ["http://localhost:5173"]}},
        supports_credentials=True,
    )

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

    @app.route("/users", methods=["POST"])
    def users_create():
        body, status = _idempotent_create(route="/users", create_fn=create_user)
        return jsonify(body), status

    @app.route("/users", methods=["GET"])
    @require_admin_api_key(ADMIN_API_KEY)
    def users_list():
        return jsonify([to_api_doc(d) for d in list_users()]), 200

    @app.route("/users/<user_id>", methods=["GET"])
    def users_get(user_id: str):
        oid = parse_object_id(user_id, "user id")
        doc = to_api_doc(get_user(oid))
        if not doc:
            raise APIError(404, "user not found")
        return jsonify(doc), 200

    @app.route("/users/<user_id>", methods=["PATCH"])
    @require_admin_api_key(ADMIN_API_KEY)
    def users_patch(user_id: str):
        oid = parse_object_id(user_id, "user id")
        updated = update_user(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/users/<user_id>", methods=["DELETE"])
    @require_admin_api_key(ADMIN_API_KEY)
    def users_delete(user_id: str):
        oid = parse_object_id(user_id, "user id")
        delete_user(oid)
        return "", 204

    @app.route("/teams", methods=["POST"])
    def teams_create():
        body, status = _idempotent_create(route="/teams", create_fn=create_team)
        return jsonify(body), status

    @app.route("/teams", methods=["GET"])
    def teams_list_route():
        return jsonify([to_api_doc(d) for d in list_teams()]), 200

    @app.route("/teams/<team_id>", methods=["GET"])
    def teams_get_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        doc = to_api_doc(get_team(oid))
        if not doc:
            raise APIError(404, "team not found")
        return jsonify(doc), 200

    @app.route("/teams/<team_id>", methods=["PATCH"])
    def teams_patch_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        updated = update_team(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/teams/<team_id>", methods=["DELETE"])
    def teams_delete_route(team_id: str):
        oid = parse_object_id(team_id, "team id")
        prune_users = request.args.get("pruneUsers", "false").lower() in {"1", "true", "yes"}
        if prune_users:
            require_admin(request.headers)
        delete_team(oid, prune_users=prune_users)
        return "", 204

    @app.route("/mailboxes", methods=["GET"])
    def mailboxes_list_route():
        return jsonify([to_api_doc(d) for d in list_mailboxes()]), 200

    @app.route("/mailboxes/<mailbox_id>", methods=["GET"])
    def mailboxes_get_route(mailbox_id: str):
        oid = parse_object_id(mailbox_id, "mailbox id")
        doc = to_api_doc(get_mailbox(oid))
        if not doc:
            raise APIError(404, "mailbox not found")
        return jsonify(doc), 200

    @app.route("/mailboxes/<mailbox_id>", methods=["PATCH"])
    def mailboxes_patch_route(mailbox_id: str):
        oid = parse_object_id(mailbox_id, "mailbox id")
        updated = update_mailbox(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/mail", methods=["POST"])
    def mail_create_route():
        body, status = _idempotent_create(route="/mail", create_fn=create_mail)
        return jsonify(body), status

    @app.route("/mail", methods=["GET"])
    def mail_list_route():
        return jsonify([to_api_doc(d) for d in list_mail()]), 200

    @app.route("/mail/<mail_id>", methods=["GET"])
    def mail_get_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        doc = to_api_doc(get_mail(oid))
        if not doc:
            raise APIError(404, "mail not found")
        return jsonify(doc), 200

    @app.route("/mail/<mail_id>", methods=["PATCH"])
    def mail_patch_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        updated = update_mail(oid, _json_payload())
        return jsonify(to_api_doc(updated)), 200

    @app.route("/mail/<mail_id>", methods=["DELETE"])
    def mail_delete_route(mail_id: str):
        oid = parse_object_id(mail_id, "mail id")
        delete_mail(oid)
        return "", 204

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
