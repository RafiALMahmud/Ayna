from datetime import timedelta

from test_workflow import create

from app.common.db import SessionLocal
from app.common.models import GenerationJob, Product, now
from app.modules.generation.tasks import recover_stale_jobs


def stale_job(product_id: str, provider: str, task_id: str | None = None) -> str:
    with SessionLocal() as db:
        product = db.get(Product, product_id)
        assert product is not None
        product.publish_status = "generating"
        job = GenerationJob(
            product_id=product_id,
            idempotency_key=f"stale-{provider}-{task_id}",
            provider=provider,
            status="processing",
            progress=25,
            heartbeat_at=now() - timedelta(hours=1),
            provenance={"provider_task_id": task_id} if task_id else {},
        )
        db.add(job)
        db.commit()
        return job.id


def test_stale_mock_and_known_hosted_tasks_are_requeued_once(client, owner):
    product = create(client, owner)
    mock_id = stale_job(product["id"], "mock")
    hosted_id = stale_job(product["id"], "meshy", "known-provider-task")
    queued = []

    result = recover_stale_jobs(queued.append, stale_before=now() - timedelta(minutes=10))

    assert result == {"requeued": 2, "failed_ambiguous": 0, "queue_failed": 0}
    assert queued == [mock_id, hosted_id]
    with SessionLocal() as db:
        for job_id in queued:
            job = db.get(GenerationJob, job_id)
            assert job is not None and job.status == "queued" and job.recovery_count == 1
        hosted = db.get(GenerationJob, hosted_id)
        assert hosted is not None
        assert hosted.provenance["recovery"]["mode"] == "provider_task_reconciliation"

    assert recover_stale_jobs(queued.append)["requeued"] == 0


def test_ambiguous_paid_submission_is_failed_not_retried(client, owner):
    product = create(client, owner)
    job_id = stale_job(product["id"], "tripo")
    queued = []

    result = recover_stale_jobs(queued.append, stale_before=now() - timedelta(minutes=10))

    assert result["failed_ambiguous"] == 1
    assert queued == []
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        product_row = db.get(Product, product["id"])
        assert job is not None and job.status == "failed"
        assert job.error_code == "AMBIGUOUS_PROVIDER_SUBMISSION"
        assert product_row is not None and product_row.publish_status == "draft"


def test_requeue_failure_leaves_safe_terminal_state(client, owner):
    product = create(client, owner)
    job_id = stale_job(product["id"], "mock")

    def unavailable(_job_id: str) -> None:
        raise OSError("simulated queue outage")

    result = recover_stale_jobs(unavailable, stale_before=now() - timedelta(minutes=10))

    assert result["queue_failed"] == 1
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        assert job is not None and job.status == "failed"
        assert job.error_code == "QUEUE_UNAVAILABLE"
