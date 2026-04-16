from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from flask import Request

from config import (
    LOGIN_RATE_LIMIT_EMAIL_MAX_ATTEMPTS,
    LOGIN_RATE_LIMIT_EMAIL_WINDOW_SECONDS,
    LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS,
    LOGIN_RATE_LIMIT_IP_WINDOW_SECONDS,
)
from repositories.login_rate_limit_repository import record_login_attempt
from validators import normalize_email, require_string


@dataclass(frozen=True)
class RateLimitScopeDecision:
    scope: str
    key: str
    count: int
    limit: int
    window_seconds: int

    @property
    def throttled(self) -> bool:
        return self.count > self.limit


@dataclass(frozen=True)
class LoginRateLimitDecision:
    client_ip: str
    email: str
    ip: RateLimitScopeDecision
    email_scope: RateLimitScopeDecision

    @property
    def allowed(self) -> bool:
        return not self.ip.throttled and not self.email_scope.throttled


def evaluate_login_rate_limit(
    *,
    request: Request,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> LoginRateLimitDecision:
    client_ip = resolve_client_ip(request)
    email = normalize_email(require_string(payload, "email", max_len=320))

    ip_decision = _record_scope(
        scope="ip",
        key=client_ip,
        limit=LOGIN_RATE_LIMIT_IP_MAX_ATTEMPTS,
        window_seconds=LOGIN_RATE_LIMIT_IP_WINDOW_SECONDS,
        now=now,
    )
    email_decision = _record_scope(
        scope="email",
        key=email,
        limit=LOGIN_RATE_LIMIT_EMAIL_MAX_ATTEMPTS,
        window_seconds=LOGIN_RATE_LIMIT_EMAIL_WINDOW_SECONDS,
        now=now,
    )
    return LoginRateLimitDecision(
        client_ip=client_ip,
        email=email,
        ip=ip_decision,
        email_scope=email_decision,
    )


def resolve_client_ip(request: Request) -> str:
    if request.access_route:
        return request.access_route[0]
    return request.remote_addr or "unknown"


def _record_scope(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
    now: datetime | None,
) -> RateLimitScopeDecision:
    bucket = record_login_attempt(
        scope=scope,
        key=key,
        window_seconds=window_seconds,
        now=now,
    )
    return RateLimitScopeDecision(
        scope=scope,
        key=key,
        count=bucket["count"],
        limit=limit,
        window_seconds=window_seconds,
    )
