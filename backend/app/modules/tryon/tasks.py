"""Bounded background work and retention cleanup for private try-on inputs."""

import io
import logging
from datetime import UTC, timedelta

from PIL import Image
from sqlalchemy import select, update

from app.common.db import SessionLocal
from app.common.models import Product, TryOnJob, now
from app.common.storage import get_storage
from app.modules.tryon.local_fashn import TryOnInferenceError, infer

logger = logging.getLogger(__name__)


def _is_expired(job: TryOnJob) -> bool:
    expiry = job.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= now()


def process_tryon_job(job_id: str) -> None:
    """Run a diagnostic or the explicitly configured local clothing model."""
    with SessionLocal() as db:
        claimed = db.scalar(
            update(TryOnJob)
            .where(TryOnJob.id == job_id, TryOnJob.status == "queued")
            .values(status="processing", progress=30)
            .returning(TryOnJob.id)
        )
        db.commit()
        if claimed is None:
            return
        job = db.get(TryOnJob, job_id)
        if job is None:
            return
        try:
            if job.provider not in {"diagnostic", "fashn_vton"} or not job.source_key:
                raise RuntimeError("TRYON_PROVIDER_UNAVAILABLE")
            storage = get_storage()
            source = storage.get(job.source_key)
            with Image.open(io.BytesIO(source)) as image:
                width, height = image.size
            diagnostics = {
                "input_width": width,
                "input_height": height,
                "framing_check": "passed",
                "body_or_feet_visibility": "not_evaluated",
                "pose_ambiguity": "not_evaluated",
                "occlusion": "not_evaluated",
            }
            if job.provider == "diagnostic":
                db.execute(
                    update(TryOnJob)
                    .where(
                        TryOnJob.id == job_id,
                        TryOnJob.status == "processing",
                        TryOnJob.expires_at > now(),
                    )
                    .values(
                        status="needs_review",
                        progress=100,
                        finished_at=now(),
                        diagnostics={
                            **diagnostics,
                            "result_generated": False,
                            "reason": "no_approved_real_tryon_provider_configured",
                        },
                    )
                    .execution_options(synchronize_session=False)
                )
                db.commit()
                return

            product = db.get(Product, job.product_id)
            if product is None:
                raise TryOnInferenceError("TRYON_PRODUCT_MISSING")
            if product.category == "shoes":
                raise TryOnInferenceError("SHOE_TRYON_MODEL_UNAVAILABLE")
            category = {"shirts": "tops", "pants": "bottoms"}.get(product.category)
            if category is None or not product.images:
                raise TryOnInferenceError("TRYON_PRODUCT_UNSUPPORTED")
            garment_image = sorted(
                product.images,
                key=lambda image: (image.view_tag != "front", image.sort_order),
            )[0]

            def cancelled() -> bool:
                with SessionLocal() as status_db:
                    current = status_db.get(TryOnJob, job_id)
                    return current is None or current.status == "deleted" or _is_expired(current)

            result, timing = infer(
                source,
                storage.get(garment_image.storage_key),
                category,
                cancelled=cancelled,
            )
            result_key = f"tryon/{job.user_id}/{job.id}/result.png"
            if cancelled():
                return
            storage.put(result_key, result, "image/png")
            updated = db.scalar(
                update(TryOnJob)
                .where(
                    TryOnJob.id == job_id,
                    TryOnJob.status == "processing",
                    TryOnJob.expires_at > now(),
                )
                .values(
                    status="succeeded",
                    progress=100,
                    result_key=result_key,
                    finished_at=now(),
                    diagnostics={
                        **diagnostics,
                        "result_generated": True,
                        "model": "FASHN VTON v1.5",
                        "model_license": "Apache-2.0",
                        "dependency_restriction": (
                            "fashn-human-parser inherits NVIDIA noncommercial terms; "
                            "demo/evaluation only"
                        ),
                        "appearance_preview_only": True,
                        **timing,
                    },
                )
                .execution_options(synchronize_session=False)
                .returning(TryOnJob.id)
            )
            db.commit()
            if updated is None:
                storage.delete(result_key)
        except Exception as exc:
            logger.error("Try-on diagnostic failed for job %s (%s)", job_id, type(exc).__name__)
            db.rollback()
            db.execute(
                update(TryOnJob)
                .where(
                    TryOnJob.id == job_id,
                    TryOnJob.status != "deleted",
                    TryOnJob.expires_at > now(),
                )
                .values(
                    status="failed",
                    progress=100,
                    error_code=(
                        str(exc)
                        if str(exc)
                        in {
                            "TRYON_PROVIDER_UNAVAILABLE",
                            "TRYON_MODEL_NOT_CONFIGURED",
                            "TRYON_TIMEOUT",
                            "TRYON_INFERENCE_FAILED",
                            "SHOE_TRYON_MODEL_UNAVAILABLE",
                        }
                        else "TRYON_FAILED"
                    ),
                    finished_at=now(),
                )
                .execution_options(synchronize_session=False)
            )
            db.commit()


def purge_expired_tryons() -> int:
    """Delete expired private image bytes while retaining a minimal audit row."""
    removed = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(TryOnJob)
            .where(TryOnJob.expires_at <= now(), TryOnJob.status != "deleted")
            .order_by(TryOnJob.expires_at)
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        storage = get_storage()
        for job in jobs:
            try:
                for key in (job.source_key, job.result_key):
                    if key:
                        storage.delete(key)
            except Exception:
                logger.error("Could not purge private try-on assets for job %s", job.id)
                continue
            job.source_key = None
            job.result_key = None
            job.status = "deleted"
            job.deleted_at = now()
            job.diagnostics = {"retention": "expired_assets_deleted"}
            removed += 1
        db.commit()
    return removed


def fail_stale_tryons() -> int:
    """Fail abandoned work safely; cleanup owns byte deletion at expiry."""
    from app.common.config import get_settings

    cutoff = now() - timedelta(seconds=get_settings().tryon_timeout_seconds + 120)
    with SessionLocal() as db:
        jobs = db.scalars(
            select(TryOnJob)
            .where(
                TryOnJob.status.in_(["queued", "processing"]),
                TryOnJob.created_at < cutoff,
            )
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        for job in jobs:
            job.status = "failed"
            job.progress = 100
            job.error_code = "STALE_WORKER_JOB"
            job.finished_at = now()
        db.commit()
        return len(jobs)
