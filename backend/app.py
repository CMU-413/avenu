from __future__ import annotations

import os
from typing import Any

import requests
from flask import Flask, jsonify, request, session

from config import (
    FRONTEND_ORIGINS,
    SCHEDULER_INTERNAL_TOKEN,
    SECRET_KEY,
    SESSION_COOKIE_PARTITIONED,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    ensure_indexes,
)
from controllers import register_blueprints
from controllers.common import json_payload
from errors import APIError
from repositories import to_api_doc
from repositories.teams_repository import find_team_by_optix_id
from repositories.users_repository import find_user_by_optix_id
from services.team_service import create_team
from services.user_service import create_user, update_user


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

    register_blueprints(app)

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
