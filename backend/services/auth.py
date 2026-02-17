from errors import APIError


def require_admin(headers: dict[str, str]) -> None:
    value = headers.get("X-Admin") or headers.get("x-admin")
    if str(value).lower() not in {"1", "true", "yes"}:
        raise APIError(403, "admin privileges required")
