"""Requeue safe stale generation work and reconcile only known hosted task IDs."""

import json

from app.modules.generation.tasks import recover_stale_jobs

if __name__ == "__main__":
    print(json.dumps(recover_stale_jobs(), sort_keys=True))
