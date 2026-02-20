from __future__ import annotations

from config import idempotency_keys_collection
from idempotency import reserve_or_replay, store_idempotent_response


def reserve_or_replay_request(*, key: str, route: str, method: str, request_hash: str) -> dict | None:
    return reserve_or_replay(
        idempotency_keys_collection,
        key=key,
        route=route,
        method=method,
        request_hash=request_hash,
    )


def store_response(*, key: str, route: str, method: str, status: int, body: dict) -> None:
    store_idempotent_response(
        idempotency_keys_collection,
        key=key,
        route=route,
        method=method,
        status=status,
        body=body,
    )


def delete_reservation(*, key: str, route: str, method: str) -> None:
    idempotency_keys_collection.delete_one({"key": key, "route": route, "method": method})
