"""Bounded background work and retention cleanup for private try-on inputs."""

import io
import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import UTC, timedelta
from functools import wraps

from PIL import Image
from sqlalchemy import select, update

from app.common.db import SessionLocal
from app.common.models import Product, TryOnJob, now
from app.common.storage import get_storage
from app.modules.tryon.local_fashn import STAGE_PROGRESS, TryOnInferenceError, infer

logger = logging.getLogger(__name__)
_GPU_JOB_LOCK = threading.Lock()


def _unload_ollama_models() -> None:
    """Best-effort release of CPU/RAM before the mixed CPU/CUDA FASHN pipeline."""
    from app.common.config import get_settings

    settings = get_settings()
    if settings.environment == "test":
        return
    requests = (
        ("generate", {"model": settings.ollama_chat_model, "keep_alive": 0}),
        (
            "embed",
            {"model": settings.ollama_embedding_model, "input": "", "keep_alive": 0},
        ),
    )
    for endpoint, payload in requests:
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{settings.ollama_base_url}/api/{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=2).close()
        except (OSError, urllib.error.URLError):
            pass


def _serialized_gpu_job(function):
    @wraps(function)
    def wrapper(job_id: str):
        with SessionLocal() as db:
            job = db.get(TryOnJob, job_id)
            use_gpu_lock = bool(job and job.provider == "fashn_vton")
        if not use_gpu_lock:
            return function(job_id)
        with _GPU_JOB_LOCK:
            _unload_ollama_models()
            return function(job_id)

    return wrapper


def _is_expired(job: TryOnJob) -> bool:
    expiry = job.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= now()


@_serialized_gpu_job
def process_tryon_job(job_id: str) -> None:
    """Run a diagnostic or the explicitly configured local clothing model."""
    with SessionLocal() as db:
        claimed = db.scalar(
            update(TryOnJob)
            .where(TryOnJob.id == job_id, TryOnJob.status == "queued")
            .values(status="processing", progress=10)
            .returning(TryOnJob.id)
        )
        db.commit()
        if claimed is None:
            return
        job = db.get(TryOnJob, job_id)
        if job is None:
            return
        job.diagnostics = {
            **job.diagnostics,
            "stage": "input_preparation",
            "stage_event": "completed",
            "stage_timings": {},
        }
        db.commit()
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
            category = {
                "shirts": "tops",
                "pants": "bottoms",
                "dresses": "one-pieces",
            }.get(product.category)
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

            def report_stage(event: dict) -> None:
                stage = str(event.get("stage", ""))
                event_type = str(event.get("event", "started"))
                if stage not in STAGE_PROGRESS or event_type not in {"started", "completed"}:
                    return
                with SessionLocal() as stage_db:
                    current = stage_db.get(TryOnJob, job_id)
                    if current is None or current.status != "processing":
                        return
                    current_diagnostics = dict(current.diagnostics)
                    timings = dict(current_diagnostics.get("stage_timings", {}))
                    elapsed = event.get("elapsed_seconds")
                    if event_type == "completed" and isinstance(elapsed, int | float):
                        timings[stage] = elapsed
                        current_diagnostics["last_completed_stage"] = stage
                    metadata = event.get("metadata")
                    if isinstance(metadata, dict):
                        allowed = {
                            "torch_version",
                            "torch_cuda",
                            "cuda_available",
                            "cuda_device",
                            "ort_version",
                            "ort_available_providers",
                            "synthesis_device",
                            "synthesis_dtype",
                            "pose_providers",
                            "pose_fallback_reason",
                            "cpu_threads",
                            "skin_recovery_applied",
                            "skin_recovery_seconds",
                            "sleeve_case",
                            "sam2_refinement",
                            "skin_tone_delta_before",
                            "skin_tone_delta_after",
                            "cuda_peak_mib",
                            "candidate_seed",
                            "parser_device",
                            "preserved_pixels",
                            "newly_exposed_skin_pixels",
                            "restoration_applied",
                            "restoration_method",
                            "restoration_seconds",
                        }
                        runtime = dict(current_diagnostics.get("runtime", {}))
                        runtime.update(
                            {key: value for key, value in metadata.items() if key in allowed}
                        )
                        current_diagnostics["runtime"] = runtime
                    current.diagnostics = {
                        **current_diagnostics,
                        "stage": stage,
                        "stage_event": event_type,
                        "stage_timings": timings,
                    }
                    current.progress = STAGE_PROGRESS[stage]
                    stage_db.commit()

            result, timing = infer(
                source,
                storage.get(garment_image.storage_key),
                category,
                cancelled=cancelled,
                job_id=job_id,
                stage_callback=report_stage,
            )
            result_key = f"tryon/{job.user_id}/{job.id}/result.png"
            if cancelled():
                return
            storage.put(result_key, result, "image/png")
            # Stage callbacks commit through independent sessions. Refresh this
            # session before the final write so those persisted timings and
            # runtime diagnostics are not replaced by the initial payload.
            db.expire_all()
            refreshed = db.get(TryOnJob, job_id)
            final_diagnostics = dict(refreshed.diagnostics) if refreshed else {}
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
                        **final_diagnostics,
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
            code = exc.code if isinstance(exc, TryOnInferenceError) else str(exc)
            allowed_codes = {
                "TRYON_PROVIDER_UNAVAILABLE",
                "TRYON_MODEL_NOT_CONFIGURED",
                "TRYON_TIMEOUT",
                "TRYON_CANCELLED",
                "TRYON_INFERENCE_FAILED",
                "TRYON_OUTPUT_MISSING",
                "TRYON_OUTPUT_INVALID",
                "SHOE_TRYON_MODEL_UNAVAILABLE",
            }
            error_code = code if code in allowed_codes else "TRYON_FAILED"
            logger.error("Try-on job %s failed with %s", job_id, error_code)
            db.rollback()
            current = db.get(TryOnJob, job_id)
            diagnostics = dict(current.diagnostics) if current else {}
            failure_details = exc.diagnostics if isinstance(exc, TryOnInferenceError) else {}
            diagnostics = {
                **diagnostics,
                **failure_details,
                "failed_stage": diagnostics.get("stage", "unknown"),
                "stage": "failed",
                "stage_event": "completed",
            }
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
                    error_code=error_code,
                    diagnostics=diagnostics,
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
