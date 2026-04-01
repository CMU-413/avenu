from __future__ import annotations

import os

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from prometheus_flask_exporter import PrometheusMetrics

from config import (
    FRONTEND_ORIGINS,
    SCHEDULER_INTERNAL_TOKEN,
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PARTITIONED,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    ensure_indexes,
)
from controllers import register_blueprints
from controllers.metrics_controller import create_metrics_blueprint
from errors import APIError


def create_app(
    *,
    testing: bool = False,
    ensure_db_indexes_on_startup: bool = True,
    secret_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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
    app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE_NAME
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

    register_blueprints(app)

    print("BOOTED APP.PY FROM", __file__)

    return app


app = create_app(testing=os.getenv("FLASK_TESTING", "").strip().lower() in {"1", "true", "yes"})
metrics = PrometheusMetrics(app, path=None)
app.register_blueprint(create_metrics_blueprint(metrics))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
