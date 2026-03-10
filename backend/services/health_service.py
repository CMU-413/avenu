from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from pymongo import MongoClient
from pymongo.errors import ConfigurationError, PyMongoError, ServerSelectionTimeoutError
from requests import ConnectionError as RequestsConnectionError
from requests import RequestException, Timeout as RequestsTimeout

from config import MONGO_URI

HealthStatus = Literal["healthy", "unreachable", "misconfigured", "error"]

HEALTHY: HealthStatus = "healthy"
UNREACHABLE: HealthStatus = "unreachable"
MISCONFIGURED: HealthStatus = "misconfigured"
ERROR: HealthStatus = "error"

DEPENDENCY_ORDER = ("mongo", "graph", "twilio")
_ALLOWED_STATUSES: set[str] = {HEALTHY, UNREACHABLE, MISCONFIGURED, ERROR}


class HealthService:
    def __init__(
        self,
        *,
        per_provider_timeout_seconds: float = 1.0,
        total_timeout_seconds: float = 3.0,
        checks: dict[str, Callable[[float], str]] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_provider_timeout_seconds = max(0.01, per_provider_timeout_seconds)
        self._total_timeout_seconds = max(0.01, total_timeout_seconds)
        self._monotonic = monotonic
        self._checks = checks or {
            "mongo": self._check_mongo,
            "graph": self._check_graph,
            "twilio": self._check_twilio,
        }

    def check_dependencies(self) -> dict[str, HealthStatus]:
        statuses: dict[str, HealthStatus] = {name: UNREACHABLE for name in DEPENDENCY_ORDER}
        deadline = self._monotonic() + self._total_timeout_seconds

        for dependency_name in DEPENDENCY_ORDER:
            remaining_seconds = deadline - self._monotonic()
            if remaining_seconds <= 0:
                statuses[dependency_name] = UNREACHABLE
                continue

            checker = self._checks[dependency_name]
            timeout_seconds = min(self._per_provider_timeout_seconds, remaining_seconds)
            statuses[dependency_name] = self._safe_check(checker=checker, timeout_seconds=timeout_seconds)

        return statuses

    def _safe_check(self, *, checker: Callable[[float], str], timeout_seconds: float) -> HealthStatus:
        try:
            result = checker(timeout_seconds)
            if result in _ALLOWED_STATUSES:
                return result  # type: ignore[return-value]
            return ERROR
        except (TimeoutError, RequestsTimeout, RequestsConnectionError, ServerSelectionTimeoutError):
            return UNREACHABLE
        except (ConfigurationError, ValueError):
            return MISCONFIGURED
        except (RequestException, PyMongoError):
            return ERROR
        except Exception:
            return ERROR

    def _check_mongo(self, timeout_seconds: float) -> HealthStatus:
        if not MONGO_URI:
            return MISCONFIGURED
        timeout_ms = max(1, int(timeout_seconds * 1000))
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
        )
        try:
            client.admin.command("ping")
            return HEALTHY
        except ConfigurationError:
            return MISCONFIGURED
        except ServerSelectionTimeoutError:
            return UNREACHABLE
        except PyMongoError:
            return ERROR
        finally:
            client.close()

    def _check_graph(self, timeout_seconds: float) -> HealthStatus:
        from services.notifications.providers.factory import build_email_provider

        provider = build_email_provider(testing=False)
        return provider.check_health(timeout_seconds=timeout_seconds)

    def _check_twilio(self, timeout_seconds: float) -> HealthStatus:
        from services.notifications.providers.factory import build_sms_provider

        provider = build_sms_provider(testing=False)
        return provider.check_health(timeout_seconds=timeout_seconds)
