from __future__ import annotations

import importlib
from typing import Any, Callable

from bson import ObjectId

from config import (
    AUTH_MAGIC_LINK_BASE_URL,
    AUTH_MAGIC_LINK_EXPIRY_SECONDS,
    AUTH_MAGIC_LINK_PATH,
    AUTH_MAGIC_LINK_SECRET,
)
from errors import APIError
from repositories.auth_magic_links_repository import get_magic_link, put_magic_link


StorageHandler = Callable[[str, dict[str, Any] | None], dict[str, Any] | None]


class AuthMagicLinkService:
    def __init__(
        self,
        *,
        base_url: str = AUTH_MAGIC_LINK_BASE_URL,
        magic_link_path: str = AUTH_MAGIC_LINK_PATH,
        link_expiry_seconds: int = AUTH_MAGIC_LINK_EXPIRY_SECONDS,
        secret_key: str = AUTH_MAGIC_LINK_SECRET,
        haze_module: Any | None = None,
        storage_handler: StorageHandler | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")
        if not normalized_base_url:
            raise RuntimeError("AUTH_MAGIC_LINK_BASE_URL must be set")
        normalized_secret_key = secret_key.strip()
        if not normalized_secret_key:
            raise RuntimeError("AUTH_MAGIC_LINK_SECRET or SECRET_KEY must be set")

        self._base_url = normalized_base_url
        self._magic_link_path = _normalize_path(magic_link_path)
        self._link_expiry_seconds = link_expiry_seconds
        self._secret_key = normalized_secret_key
        self._storage_handler = storage_handler or _default_storage_handler
        self._haze = haze_module or importlib.import_module("haze")

        self._haze.use(
            base_url=self._base_url,
            magic_link_path=self._magic_link_path,
            link_expiry=self._link_expiry_seconds,
            allow_reuse=False,
            secret_key=self._secret_key,
            token_provider="jwt",
        )
        self._haze.storage(self._storage_handler)

    def generate_admin_login_link(
        self,
        *,
        user: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        expiry_seconds: int | None = None,
    ) -> str:
        if user.get("isAdmin") is not True:
            raise APIError(403, "forbidden")

        user_id = _require_user_id(user)
        resolved_metadata = {
            "email": user.get("email", ""),
            "fullname": user.get("fullname", ""),
            **(metadata or {}),
        }
        return self._haze.generate(
            user_id=user_id,
            metadata=resolved_metadata,
            expiry=expiry_seconds,
        )

    def verify_login_link(self, *, token_id: str, signature: str) -> dict[str, Any]:
        result = self._haze.verify(token_id, signature)
        user_id = result.get("user_id")
        if not isinstance(user_id, str) or not ObjectId.is_valid(user_id):
            raise APIError(401, "unauthorized")
        return {
            "userId": ObjectId(user_id),
            "tokenId": result.get("token_id", token_id),
            "metadata": result.get("metadata", {}),
            "exp": result.get("exp"),
            "iat": result.get("iat"),
        }


def _default_storage_handler(token_id: str, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if data is None:
        return get_magic_link(token_id)
    return put_magic_link(token_id, data)


def _normalize_path(path: str) -> str:
    normalized = (path or "/").strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _require_user_id(user: dict[str, Any]) -> str:
    raw = user.get("_id")
    if isinstance(raw, ObjectId):
        return str(raw)
    if isinstance(raw, str) and ObjectId.is_valid(raw):
        return raw
    raise APIError(500, "user missing valid _id")
