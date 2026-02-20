from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from repositories.users_repository import list_opted_in_user_ids
from services.notifications.interfaces import Notifier
from services.notifications.types import WeeklyCronJobResult


def compute_previous_week_range(now: datetime) -> tuple[date, date]:
    if now.tzinfo is None:
        utc_now = now.replace(tzinfo=timezone.utc)
    else:
        utc_now = now.astimezone(timezone.utc)

    today = utc_now.date()
    days_since_monday = today.weekday()
    current_week_start = today - timedelta(days=days_since_monday)
    previous_week_start = current_week_start - timedelta(days=7)
    previous_week_end = current_week_start - timedelta(days=1)
    return previous_week_start, previous_week_end


def run_weekly_summary_cron_job(
    *,
    notifier: Notifier,
    users=None,
    now: datetime | None = None,
    week_start: date | None = None,
    week_end: date | None = None,
    logger: logging.Logger | None = None,
) -> WeeklyCronJobResult:
    resolved_now = now or datetime.now(tz=timezone.utc)
    if (week_start is None) != (week_end is None):
        raise ValueError("week_start and week_end must be provided together")
    if week_start is None:
        resolved_week_start, resolved_week_end = compute_previous_week_range(resolved_now)
    else:
        if week_end < week_start:
            raise ValueError("week_end must be on or after week_start")
        resolved_week_start, resolved_week_end = week_start, week_end
    log = logger or logging.getLogger(__name__)
    started_at = perf_counter()

    if users is None:
        opted_in_user_ids = list_opted_in_user_ids(preference="email")
    else:
        opted_in_user_ids = [doc["_id"] for doc in users.find({"notifPrefs": {"$in": ["email"]}}, {"_id": 1})]
    candidate_count = len(opted_in_user_ids)

    counters: WeeklyCronJobResult = {
        "weekStart": resolved_week_start,
        "weekEnd": resolved_week_end,
        "processed": 0,
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "errors": 0,
    }

    log.info(
        "weekly_summary_cron_job_start weekStart=%s weekEnd=%s candidates=%d",
        resolved_week_start.isoformat(),
        resolved_week_end.isoformat(),
        candidate_count,
    )

    for user_id in opted_in_user_ids:
        counters["processed"] += 1
        try:
            result = notifier.notifyWeeklySummary(
                userId=user_id,
                weekStart=resolved_week_start,
                weekEnd=resolved_week_end,
                triggeredBy="cron",
            )
            status = result.get("status")
            if status == "sent":
                counters["sent"] += 1
            elif status == "skipped":
                counters["skipped"] += 1
            elif status == "failed":
                counters["failed"] += 1
            else:
                counters["errors"] += 1
                log.error("weekly_summary_cron_job_invalid_status userId=%s status=%r", user_id, status)
        except Exception:
            counters["errors"] += 1
            log.exception("weekly_summary_cron_job_user_exception userId=%s", user_id)

    elapsed_seconds = perf_counter() - started_at
    log.info(
        (
            "weekly_summary_cron_job_complete weekStart=%s weekEnd=%s processed=%d sent=%d "
            "skipped=%d failed=%d errors=%d elapsedSeconds=%.3f"
        ),
        resolved_week_start.isoformat(),
        resolved_week_end.isoformat(),
        counters["processed"],
        counters["sent"],
        counters["skipped"],
        counters["failed"],
        counters["errors"],
        elapsed_seconds,
    )
    return counters
