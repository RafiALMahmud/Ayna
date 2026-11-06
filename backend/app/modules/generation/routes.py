from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import func, select, text

from app.common.auth import seller_id
from app.common.config import get_settings
from app.common.db import get_db
from app.common.models import GenerationJob, Product, now
from app.common.schemas import JobOut
from app.common.views import job_out
from app.modules.catalog.routes import owned_product
from app.modules.generation.tasks import process_job, queue

router = APIRouter(tags=["Generation"])


@router.get("/products/{product_id}/generation-jobs", response_model=list[JobOut])
def list_jobs(product_id: UUID, owner: str = Depends(seller_id), db=Depends(get_db)):
    product = owned_product(db, product_id, owner)
    jobs = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.product_id == product.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(20)
    )
    return [job_out(job, owner) for job in jobs]


@router.post("/products/{product_id}/generation-jobs", response_model=JobOut, status_code=202)
def start_generation(
    product_id: UUID,
    background: BackgroundTasks,
    idempotency_key: str = Header(min_length=1, max_length=128),
    owner: str = Depends(seller_id),
    db=Depends(get_db),
):
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    else:
        # Serialize the quota check across API instances, including different products.
        db.execute(text("SELECT pg_advisory_xact_lock(18042026)"))
    product = owned_product(db, product_id, owner, lock=True)
    existing = db.scalar(
        select(GenerationJob).where(
            GenerationJob.product_id == product.id, GenerationJob.idempotency_key == idempotency_key
        )
    )
    if existing:
        return job_out(existing, owner)
    if product.publish_status == "generating":
        raise HTTPException(409, "A generation is already active")
    settings = get_settings()
    if not settings.min_images <= len(product.images) <= settings.max_images:
        raise HTTPException(422, "Upload 2–5 images before generation")
    recent = select(GenerationJob).where(GenerationJob.created_at >= now() - timedelta(days=1))
    seller_jobs = (
        db.scalar(
            select(func.count()).select_from(
                recent.join(Product, Product.id == GenerationJob.product_id)
                .where(Product.seller_id == owner)
                .subquery()
            )
        )
        or 0
    )
    if seller_jobs >= settings.generation_seller_daily_limit:
        raise HTTPException(429, "Your daily generation request limit has been reached")
    if settings.ai_provider in {"meshy", "tripo"}:
        limit = (
            settings.meshy_daily_request_limit
            if settings.ai_provider == "meshy"
            else settings.tripo_daily_request_limit
        )
        key = settings.meshy_api_key if settings.ai_provider == "meshy" else settings.tripo_api_key
        used = (
            db.scalar(
                select(func.count()).select_from(
                    recent.where(GenerationJob.provider == settings.ai_provider).subquery()
                )
            )
            or 0
        )
        if not key or used >= limit:
            raise HTTPException(429, "Hosted generation is disabled or its daily cap is exhausted")
    job = GenerationJob(
        product_id=product.id, idempotency_key=idempotency_key, provider=settings.ai_provider
    )
    product.publish_status = "generating"
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        if settings.queue_mode == "inline":
            background.add_task(process_job, job.id)
        else:
            queue().enqueue(
                process_job,
                job.id,
                job_id=job.id,
                result_ttl=86400,
                job_timeout=max(settings.meshy_timeout_seconds, settings.tripo_timeout_seconds)
                + 180,
            )
    except Exception as exc:
        job.status, job.error_code, job.finished_at = "failed", "QUEUE_UNAVAILABLE", now()
        product.publish_status = "draft"
        db.commit()
        raise HTTPException(503, "Queue unavailable; retry with a new idempotency key") from exc
    return job_out(job, owner)


@router.get("/generation-jobs/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, owner: str = Depends(seller_id), db=Depends(get_db)):
    job = db.get(GenerationJob, str(job_id))
    if job is None:
        raise HTTPException(404, "Job not found")
    owned_product(db, job.product_id, owner)
    return job_out(job, owner)
