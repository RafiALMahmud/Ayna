import logging
import os
import threading

from redis import Redis
from rq import SimpleWorker, Worker

from app.common.config import get_settings
from app.modules.generation.tasks import recover_stale_jobs
from app.modules.tryon.tasks import fail_stale_tryons, purge_expired_tryons

logger = logging.getLogger(__name__)


def maintain(stop: threading.Event) -> None:
    settings = get_settings()
    while not stop.wait(settings.maintenance_interval_seconds):
        try:
            recover_stale_jobs()
            fail_stale_tryons()
            purge_expired_tryons()
        except Exception:
            logger.exception("Periodic worker maintenance failed")


def main():
    recover_stale_jobs()
    fail_stale_tryons()
    purge_expired_tryons()
    # Windows native development only; Docker always uses process-isolated Worker.
    worker_class = SimpleWorker if os.name == "nt" else Worker
    # RQ blocks for worker_ttl - 15 seconds while idle. Refresh within the
    # health probe's 120-second freshness window even when no jobs arrive.
    stop = threading.Event()
    maintenance = threading.Thread(target=maintain, args=(stop,), daemon=True)
    maintenance.start()
    try:
        worker_class(
            ["ayna"], connection=Redis.from_url(get_settings().redis_url), worker_ttl=60
        ).work()
    finally:
        stop.set()
        maintenance.join(timeout=5)


if __name__ == "__main__":
    main()
