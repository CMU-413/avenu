from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

from scheduler.client import BackendClient, BackendClientError
from scheduler.config import load_config


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("scheduler")
    config = load_config()
    client = BackendClient(config.backend_api_url)
    last_processed_minute: str | None = None

    logger.info(
        "scheduler_started backend=%s cron=%s timezone=%s tick_seconds=%d",
        config.backend_api_url,
        config.cron_expression,
        config.timezone.key,
        config.tick_seconds,
    )
    while True:
        now_utc = datetime.now(tz=timezone.utc)
        local_now = now_utc.astimezone(config.timezone).replace(second=0, microsecond=0)
        minute_key = local_now.strftime("%Y-%m-%dT%H:%M")
        if minute_key != last_processed_minute and config.schedule.matches(local_now):
            week_start, week_end = compute_previous_week_range(now_utc)
            idempotency_key = f"weekly-summary:{week_start.isoformat()}"
            try:
                result = client.trigger_weekly_summary(
                    scheduler_token=config.scheduler_token,
                    week_start=week_start,
                    week_end=week_end,
                    idempotency_key=idempotency_key,
                )
                logger.info(
                    (
                        "weekly_summary_trigger_success weekStart=%s weekEnd=%s processed=%s sent=%s "
                        "skipped=%s failed=%s errors=%s"
                    ),
                    week_start.isoformat(),
                    week_end.isoformat(),
                    result.get("processed"),
                    result.get("sent"),
                    result.get("skipped"),
                    result.get("failed"),
                    result.get("errors"),
                )
            except BackendClientError as exc:
                logger.exception(
                    "weekly_summary_trigger_failed weekStart=%s weekEnd=%s detail=%s",
                    week_start.isoformat(),
                    week_end.isoformat(),
                    str(exc),
                )
            last_processed_minute = minute_key
        time.sleep(config.tick_seconds)


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


if __name__ == "__main__":
    raise SystemExit(main())
