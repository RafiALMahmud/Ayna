import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from redis import Redis
from rq import Queue
from sqlalchemy import select, update

from app.common.config import get_settings
from app.common.db import SessionLocal
from app.common.models import GenerationJob, Product, now
from app.common.storage import get_storage
from app.modules.generation.blender import optimize_with_blender
from app.modules.generation.local_triposr import LocalTripoSRProvider
from app.modules.generation.meshy import MeshyProvider, ProviderError, select_views, validate_glb
from app.modules.generation.providers import MockProvider
from app.modules.generation.tripo import TripoProvider, select_tripo_views
from app.modules.quality.service import build_quality_artifacts

logger = logging.getLogger(__name__)


def queue() -> Queue:
    return Queue("ayna", connection=Redis.from_url(get_settings().redis_url), default_timeout=120)


def process_job(job_id: str) -> None:
    """Claim once, persist a deterministic artifact, then create an honest quality report."""
    with SessionLocal() as db:
        claimed = db.scalar(
            update(GenerationJob)
            .where(GenerationJob.id == job_id, GenerationJob.status == "queued")
            .values(status="processing", progress=15, heartbeat_at=now())
            .returning(GenerationJob.id)
        )
        db.commit()
        if claimed is None:
            return
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        try:
            product = db.get(Product, job.product_id)
            if product is None:
                raise ValueError("Product missing")

            def submitted(task_id: str):
                job.provenance = {
                    **(job.provenance or {}),
                    "provider_task_id": task_id,
                    "provider": job.provider,
                }
                job.heartbeat_at = now()
                db.commit()

            def progress(value: int):
                job.progress, job.heartbeat_at = value, now()
                db.commit()

            def cancelled() -> bool:
                # Observe cancellation without relying on this long-lived session's cache.
                with SessionLocal() as status_db:
                    current = status_db.get(GenerationJob, job_id)
                    return current is None or current.status == "cancelled"

            existing_task_id = (job.provenance or {}).get("provider_task_id")
            if not isinstance(existing_task_id, str):
                existing_task_id = None

            if job.provider == "mock":
                result = MockProvider().generate([i.storage_key for i in product.images])
            elif job.provider == "local_triposr":
                ordered = sorted(
                    product.images,
                    key=lambda image: (image.view_tag != "front", image.sort_order),
                )
                result = LocalTripoSRProvider(progress=progress, cancelled=cancelled).generate(
                    [image.storage_key for image in ordered]
                )
            elif job.provider == "meshy":
                result = MeshyProvider(submitted=submitted, progress=progress).generate(
                    [i.storage_key for i in select_views(product.images)],
                    existing_task_id=existing_task_id,
                )
            elif job.provider == "tripo":
                result = TripoProvider(submitted=submitted, progress=progress).generate(
                    select_tripo_views(product.images),
                    existing_task_id=existing_task_id,
                )
            else:
                raise ProviderError("PROVIDER_NOT_CONFIGURED")
            if cancelled():
                db.rollback()
                db.execute(
                    update(Product)
                    .where(Product.id == job.product_id, Product.publish_status == "generating")
                    .values(publish_status="draft")
                )
                db.commit()
                return
            validate_glb(result.glb)
            optimization = optimize_with_blender(result.glb) if job.provider != "mock" else None
            published_glb = optimization.glb if optimization else result.glb
            filename = "dummy.glb" if job.provider == "mock" else "model.glb"
            key = f"models/{job.id}/{filename}"
            storage = get_storage()
            original_key = None
            if optimization and optimization.metadata["status"] == "optimized":
                original_key = f"models/{job.id}/original.glb"
                storage.put(original_key, optimization.original_glb, "model/gltf-binary")
            storage.put(key, published_glb, "model/gltf-binary")
            quality = build_quality_artifacts(
                product,
                job,
                model_glb=published_glb,
                # The mock octahedron is intentionally unrelated to uploaded photos.
                evaluate_rendered_views=job.provider != "mock",
            )
            render_keys: dict[str, str] = {}
            render_storage_failures: dict[str, str] = {}
            for view, png in quality.rendered_views.items():
                render_key = f"models/{job.id}/quality/{view}.png"
                try:
                    storage.put(render_key, png, "image/png")
                    render_keys[view] = render_key
                except Exception as exc:
                    logger.warning("Could not store %s quality render for job %s", view, job.id)
                    render_storage_failures[view] = exc.__class__.__name__
            provenance = {
                **(job.provenance or {}),
                **result.metadata,
                "optimization": optimization.metadata
                if optimization
                else {"status": "not_applicable"},
                "original_model_key": original_key,
                "input_image_ids": [image.id for image in product.images],
                "quality_rendering": quality.render_metadata,
                "quality_render_keys": render_keys,
                "quality_render_storage_failures": render_storage_failures,
            }
            updated = db.scalar(
                update(GenerationJob)
                .where(GenerationJob.id == job_id, GenerationJob.status == "processing")
                .values(
                    model_key=key,
                    provenance=provenance,
                    status="succeeded",
                    progress=100,
                    finished_at=now(),
                    heartbeat_at=now(),
                )
                .returning(GenerationJob.id)
            )
            if updated is None:
                db.rollback()
                for stored_key in [key, original_key, *render_keys.values()]:
                    if stored_key:
                        storage.delete(stored_key)
                return
            product.publish_status = "needs_review"
            # Deterministic screenshots are useful for inspection, but mock geometry has no
            # correspondence to the seller photos and therefore stays not_evaluated.
            db.add(quality.report)
            db.commit()
        except Exception as exc:
            # Do not log provider responses, URLs, uploaded photographs or credentials.
            logger.error("Generation failed for job %s (%s)", job_id, type(exc).__name__)
            db.rollback()
            current = db.get(GenerationJob, job_id)
            if current is None or current.status == "cancelled":
                return
            db.execute(
                update(GenerationJob)
                .where(GenerationJob.id == job_id)
                .values(
                    status="failed",
                    error_code=str(exc) if isinstance(exc, ProviderError) else "GENERATION_FAILED",
                    finished_at=now(),
                    heartbeat_at=now(),
                    model_key=None,
                )
            )
            db.execute(
                update(Product).where(Product.id == job.product_id).values(publish_status="draft")
            )
            db.commit()


def recover_stale_jobs(
    enqueue: Callable[[str], None] | None = None,
    *,
    stale_before: datetime | None = None,
) -> dict[str, int]:
    """Recover stale work once without repeating an ambiguous paid submission."""
    settings = get_settings()
    cutoff = stale_before or now() - timedelta(seconds=settings.generation_stale_seconds)
    counts = {"requeued": 0, "failed_ambiguous": 0, "queue_failed": 0}
    to_enqueue: list[str] = []
    with SessionLocal() as db:
        jobs = db.scalars(
            select(GenerationJob)
            .where(
                GenerationJob.status.in_(["queued", "processing"]),
                GenerationJob.heartbeat_at < cutoff,
            )
            .order_by(GenerationJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        for job in jobs:
            task_id = (job.provenance or {}).get("provider_task_id")
            if job.provider in {"meshy", "tripo"} and job.status == "processing" and not task_id:
                job.status = "failed"
                job.error_code = "AMBIGUOUS_PROVIDER_SUBMISSION"
                job.finished_at = now()
                product = db.get(Product, job.product_id)
                if product:
                    product.publish_status = "draft"
                counts["failed_ambiguous"] += 1
                continue
            job.status = "queued"
            job.error_code = None
            job.heartbeat_at = now()
            job.recovery_count += 1
            job.provenance = {
                **(job.provenance or {}),
                "recovery": {
                    "count": job.recovery_count,
                    "mode": "provider_task_reconciliation" if task_id else "safe_requeue",
                },
            }
            to_enqueue.append(job.id)
            counts["requeued"] += 1
        db.commit()

    def send(job_id: str) -> None:
        if enqueue is not None:
            enqueue(job_id)
            return
        queue().enqueue(
            process_job,
            job_id,
            job_id=job_id,
            result_ttl=86400,
            job_timeout=max(
                settings.meshy_timeout_seconds,
                settings.tripo_timeout_seconds,
                settings.local_triposr_timeout_seconds,
            )
            + 180,
        )

    for job_id in to_enqueue:
        try:
            send(job_id)
        except Exception:
            logger.error("Could not requeue stale generation job %s", job_id)
            with SessionLocal() as db:
                recovered_job = db.get(GenerationJob, job_id)
                if recovered_job and recovered_job.status == "queued":
                    recovered_job.status = "failed"
                    recovered_job.error_code = "QUEUE_UNAVAILABLE"
                    recovered_job.finished_at = now()
                    product = db.get(Product, recovered_job.product_id)
                    if product:
                        product.publish_status = "draft"
                    db.commit()
            counts["queue_failed"] += 1
    return counts


def latest_job(db, product_id: str):
    return db.scalar(
        select(GenerationJob)
        .where(GenerationJob.product_id == product_id)
        .order_by(GenerationJob.created_at.desc())
        .limit(1)
    )
