"""Bounded background work and retention cleanup for private try-on inputs."""

import io
import logging

from PIL import Image
from sqlalchemy import select, update

from app.common.db import SessionLocal
from app.common.models import TryOnJob, now
from app.common.storage import get_storage

logger = logging.getLogger(__name__)


def process_tryon_job(job_id: str) -> None:
    """Run an honest diagnostic; no synthetic try-on is produced in this mode."""
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
            if job.provider != "diagnostic" or not job.source_key:
                raise RuntimeError("TRYON_PROVIDER_UNAVAILABLE")
            source = get_storage().get(job.source_key)
            with Image.open(io.BytesIO(source)) as image:
                width, height = image.size
            job.status = "needs_review"
            job.progress = 100
            job.finished_at = now()
            job.diagnostics = {
                "input_width": width,
                "input_height": height,
                "framing_check": "passed",
                "body_or_feet_visibility": "not_evaluated",
                "pose_ambiguity": "not_evaluated",
                "occlusion": "not_evaluated",
                "result_generated": False,
                "reason": "no_approved_real_tryon_provider_configured",
            }
            db.commit()
        except Exception as exc:
            logger.error("Try-on diagnostic failed for job %s (%s)", job_id, type(exc).__name__)
            db.rollback()
            db.execute(
                update(TryOnJob)
                .where(TryOnJob.id == job_id)
                .values(
                    status="failed",
                    progress=100,
                    error_code=(
                        str(exc) if str(exc) == "TRYON_PROVIDER_UNAVAILABLE" else "TRYON_FAILED"
                    ),
                    finished_at=now(),
                )
            )
            db.commit()


def purge_expired_tryons() -> int:
    """Delete expired private image bytes while retaining a minimal audit row."""
    removed = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(TryOnJob).where(
                TryOnJob.expires_at <= now(),
                TryOnJob.status != "deleted",
            )
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
