"""Staff authentication via API key."""

from functools import wraps

from flask import request, jsonify


def _extract_admin_key() -> str | None:
    """Extract admin API key from Authorization header or X-Admin-Key."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return request.headers.get("X-Admin-Key") or None


def require_admin(admin_api_key: str):
    """Decorator that requires valid admin API key; returns 401 otherwise."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not admin_api_key:
                return jsonify({"error": "admin authentication not configured"}), 503
            key = _extract_admin_key()
            if not key or key != admin_api_key:
                return jsonify({"error": "unauthorized"}), 401
            return f(*args, **kwargs)

        return wrapped

    return decorator
