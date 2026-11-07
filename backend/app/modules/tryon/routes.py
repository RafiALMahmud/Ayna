import io
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from PIL import Image
from redis import Redis
from rq import Queue
from sqlalchemy import select

from app.common.config import get_settings
from app.common.db import get_db
from app.common.identity import current_user, throttle
from app.common.models import TryOnJob, now
from app.common.storage import get_storage
from app.modules.catalog.routes import sanitize_image
from app.modules.commerce.service import listed
from app.modules.tryon.schemas import TryOnOut
from app.modules.tryon.tasks import process_tryon_job

router = APIRouter(prefix="/try-on", tags=["Private virtual try-on"])
SUPPORTED = {"shirts": {"upper_body", "full_body"}, "pants": {"full_body"}, "shoes": {"full_body"}}


def owned_job(db, job_id: UUID | str, user_id: str) -> TryOnJob:
    job = db.scalar(select(TryOnJob).where(TryOnJob.id == str(job_id), TryOnJob.user_id == user_id))
    if job is None:
        raise HTTPException(404, "Try-on job not found")
    return job


def output(job: TryOnJob) -> TryOnOut:
    result = TryOnOut.model_validate(job)
    if job.provider == "fashn_vton":
        result.mode = "generated_preview"
        result.disclosure = (
            "AI-generated appearance preview only; it does not predict sizing or physical fit. "
            "This demo model has a noncommercial parser dependency."
        )
    else:
        result.disclosure = (
            "Diagnostic mode checks framing and privacy workflow only; no try-on is generated."
        )
    if job.status == "succeeded" and job.result_key:
        result.result_url = f"/api/v1/try-on/jobs/{job.id}/result"
    return result


def enqueue(job_id: str) -> None:
    settings = get_settings()
    if settings.queue_mode == "inline":
        process_tryon_job(job_id)
        return
    Queue(
        "ayna",
        connection=Redis.from_url(settings.redis_url),
        default_timeout=settings.tryon_timeout_seconds,
    ).enqueue(
        process_tryon_job,
        job_id,
        job_id=f"tryon-{job_id}",
        job_timeout=settings.tryon_timeout_seconds + 60,
        result_ttl=3600,
    )


@router.post("/products/{product_id}/jobs", response_model=TryOnOut, status_code=202)
async def create_job(
    product_id: UUID,
    photo: UploadFile = File(...),
    framing: Literal["upper_body", "full_body"] = Form(...),
    consent: bool = Form(...),
    no_training: bool = Form(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(current_user),
    db=Depends(get_db),
):
    settings = get_settings()
    if settings.tryon_provider == "disabled":
        raise HTTPException(503, "Virtual try-on is not configured")
    product = listed(db, str(product_id))
    allowed_framing = SUPPORTED.get(product.category)
    if not allowed_framing:
        raise HTTPException(422, "Virtual try-on is available only for shirts, pants, and shoes")
    if settings.tryon_provider == "fashn_vton" and product.category == "shoes":
        raise HTTPException(
            422,
            "Local shoe try-on is unavailable: the configured model supports clothing only",
        )
    if framing not in allowed_framing:
        raise HTTPException(422, f"{product.category} try-on requires full-body framing")
    if product.category not in SUPPORTED:
        raise HTTPException(422, "Try-on is available only for supported clothing and shoes")
    if framing not in SUPPORTED[product.category]:
        raise HTTPException(422, f"{product.category} requires full-body framing")
    if not consent or not no_training:
        raise HTTPException(422, "Explicit consent and no-training acknowledgement are required")
    existing = db.scalar(
        select(TryOnJob).where(
            TryOnJob.user_id == user.id,
            TryOnJob.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return output(existing)
    throttle(db, f"tryon:{user.id}", 20)
    raw = await photo.read(settings.tryon_max_image_bytes + 1)
    await photo.close()
    if len(raw) > settings.tryon_max_image_bytes:
        raise HTTPException(413, "Try-on photo exceeds the byte limit")
    sanitized = sanitize_image(raw, photo.content_type)
    with Image.open(io.BytesIO(sanitized)) as image:
        width, height = image.size
    if min(width, height) < 512:
        raise HTTPException(422, "Use a clear photo at least 512 pixels on its shortest side")
    if framing == "full_body" and width / height > 0.9:
        raise HTTPException(422, "Full-body try-on requires a portrait photo showing head to feet")
    created = now()
    job = TryOnJob(
        user_id=user.id,
        product_id=product.id,
        idempotency_key=idempotency_key,
        provider=settings.tryon_provider,
        framing=framing,
        consent_at=created,
        no_training=True,
        status="queued",
        progress=0,
        diagnostics={"upload": "metadata_stripped", "training_use": False},
        expires_at=created + timedelta(hours=settings.tryon_retention_hours),
    )
    db.add(job)
    db.flush()
    job.source_key = f"tryon/{user.id}/{job.id}/source.png"
    get_storage().put(job.source_key, sanitized, "image/png")
    db.commit()
    try:
        enqueue(job.id)
    except Exception as exc:
        job.status = "failed"
        job.progress = 100
        job.error_code = "QUEUE_UNAVAILABLE"
        job.finished_at = now()
        db.commit()
        raise HTTPException(503, "Try-on worker is unavailable; you can delete the upload") from exc
    db.refresh(job)
    return output(job)


@router.get("/jobs/{job_id}", response_model=TryOnOut)
def get_job(job_id: UUID, user=Depends(current_user), db=Depends(get_db)):
    return output(owned_job(db, job_id, user.id))


@router.get("/jobs/{job_id}/result")
def get_result(job_id: UUID, user=Depends(current_user), db=Depends(get_db)):
    job = owned_job(db, job_id, user.id)
    if job.status != "succeeded" or not job.result_key:
        raise HTTPException(404, "Try-on result is not available")
    try:
        return Response(get_storage().get(job.result_key), media_type="image/png")
    except Exception as exc:
        raise HTTPException(404, "Try-on result is unavailable") from exc


@router.delete("/jobs/{job_id}", response_model=TryOnOut)
def delete_job(job_id: UUID, user=Depends(current_user), db=Depends(get_db)):
    job = owned_job(db, job_id, user.id)
    try:
        for key in (job.source_key, job.result_key):
            if key:
                get_storage().delete(key)
    except Exception as exc:
        raise HTTPException(503, "Private try-on assets could not be deleted") from exc
    job.source_key = None
    job.result_key = None
    job.status = "deleted"
    job.progress = 100
    job.deleted_at = now()
    job.diagnostics = {"user_deleted": True}
    db.commit()
    db.refresh(job)
    return output(job)
