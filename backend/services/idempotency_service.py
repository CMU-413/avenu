from __future__ import annotations

from typing import Any

from idempotency import payload_hash, require_idempotency_key
from repositories.idempotency_repository import delete_reservation, reserve_or_replay_request, store_response


def begin_request(*, headers: dict[str, str], payload: dict[str, Any], route: str, method: str) -> tuple[str, dict[str, Any] | None]:
    key = require_idempotency_key(headers)
    request_hash = payload_hash(payload)
    replay = reserve_or_replay_request(
        key=key,
        route=route,
        method=method,
        request_hash=request_hash,
    )
    return key, replay


def commit_response(*, key: str, route: str, method: str, status: int, body: dict[str, Any]) -> None:
    store_response(key=key, route=route, method=method, status=status, body=body)


def rollback_reservation(*, key: str, route: str, method: str) -> None:
    delete_reservation(key=key, route=route, method=method)
