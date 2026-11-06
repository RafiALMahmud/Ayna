import os

from redis import Redis
from rq import SimpleWorker, Worker

from app.common.config import get_settings
from app.modules.generation.tasks import recover_stale_jobs
from app.modules.tryon.tasks import purge_expired_tryons


def main():
    recover_stale_jobs()
    purge_expired_tryons()
    # Windows native development only; Docker always uses process-isolated Worker.
    worker_class = SimpleWorker if os.name == "nt" else Worker
    # RQ blocks for worker_ttl - 15 seconds while idle. Refresh within the
    # health probe's 120-second freshness window even when no jobs arrive.
    worker_class(
        ["ayna"], connection=Redis.from_url(get_settings().redis_url), worker_ttl=60
    ).work()


if __name__ == "__main__":
    main()
