from __future__ import annotations

import logging
import time

from scheduler.client import BackendClient
from scheduler.config import load_config


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("scheduler")
    config = load_config()
    client = BackendClient(config.backend_api_url)

    logger.info("scheduler_started backend=%s poll_seconds=%d", config.backend_api_url, config.poll_seconds)
    while True:
        healthy, detail = client.check_health()
        if healthy:
            logger.info("backend_health_check status=healthy")
        else:
            logger.warning("backend_health_check status=unhealthy detail=%s", detail)
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
