"""Session-backed authentication and admin authorization."""

from functools import wraps

from bson import ObjectId
from flask import jsonify, session

from errors import APIError
from repositories import find_user


def _current_session_user() -> dict | None:
    raw_user_id = session.get("user_id")
    if not isinstance(raw_user_id, str) or not ObjectId.is_valid(raw_user_id):
        return None
    return find_user(ObjectId(raw_user_id))


def current_session_user() -> dict | None:
    return _current_session_user()


def require_admin_session(fn):
    """Decorator that requires authenticated admin user in session."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = _current_session_user()
        if user is None:
            return jsonify({"error": "unauthorized"}), 401
        if user.get("isAdmin") is not True:
            return jsonify({"error": "forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapped


def ensure_session_user() -> dict:
    user = _current_session_user()
    if user is None:
        raise APIError(401, "unauthorized")
    return user


def ensure_admin_session() -> None:
    user = ensure_session_user()
    if user.get("isAdmin") is not True:
        raise APIError(403, "forbidden")


def ensure_member_session() -> dict:
    user = ensure_session_user()
    if user.get("isAdmin") is True:
        raise APIError(403, "forbidden")
    return user
