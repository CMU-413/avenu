from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerConfig:
    backend_api_url: str
    poll_seconds: int


def load_config() -> SchedulerConfig:
    backend_api_url = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
    poll_seconds = int(os.getenv("SCHEDULER_POLL_SECONDS", "60"))
    if poll_seconds < 5:
        poll_seconds = 5
    return SchedulerConfig(backend_api_url=backend_api_url, poll_seconds=poll_seconds)
