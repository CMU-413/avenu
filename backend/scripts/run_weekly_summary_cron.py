from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from services.notifications.channels.email_channel import EmailChannel
from services.notifications.interfaces import Notifier
from services.notifications.providers.console_provider import ConsoleEmailProvider
from services.notifications.types import WeeklyCronJobResult
from services.notifications.weekly_summary_cron_job import run_weekly_summary_cron_job
from services.notifications.weekly_summary_notifier import WeeklySummaryNotifier


def _is_testing_mode() -> bool:
    raw = os.getenv("FLASK_TESTING", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_default_notifier() -> Notifier:
    return WeeklySummaryNotifier(channels=[EmailChannel(ConsoleEmailProvider())])


def run_weekly_summary_cron_command(
    *,
    notifier: Notifier | None = None,
    now: datetime | None = None,
    logger: logging.Logger | None = None,
    job_runner: Callable[..., WeeklyCronJobResult] = run_weekly_summary_cron_job,
    app_factory: Callable[..., object] = create_app,
) -> WeeklyCronJobResult:
    resolved_notifier = notifier or build_default_notifier()
    app = app_factory(testing=_is_testing_mode(), ensure_db_indexes_on_startup=not _is_testing_mode())
    with app.app_context():
        return job_runner(notifier=resolved_notifier, now=now, logger=logger)


def main() -> int:
    result = run_weekly_summary_cron_command()
    print(
        (
            "weekly_summary_cron_command_complete "
            f"weekStart={result['weekStart'].isoformat()} "
            f"weekEnd={result['weekEnd'].isoformat()} "
            f"processed={result['processed']} sent={result['sent']} "
            f"skipped={result['skipped']} failed={result['failed']} errors={result['errors']}"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
