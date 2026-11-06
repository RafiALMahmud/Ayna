from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.db import Base


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "publish_status IN ('draft','generating','needs_review','approved','rejected')",
            name="product_publish_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(3000), default="")
    price_minor: Mapped[int] = mapped_column(default=0, server_default="0")
    compare_at_minor: Mapped[int | None]
    stock: Mapped[int] = mapped_column(default=0, server_default="0")
    brand: Mapped[str] = mapped_column(String(100), default="", server_default="")
    sku: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    is_listed: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    featured: Mapped[bool] = mapped_column(default=False, server_default=false())
    publish_status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    images: Mapped[list["ProductImage"]] = relationship(
        cascade="all, delete-orphan", order_by="ProductImage.sort_order", lazy="selectin"
    )


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255))
    original_key: Mapped[str] = mapped_column(String(255))
    view_tag: Mapped[str] = mapped_column(String(32), default="unspecified")
    sort_order: Mapped[int]


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint("product_id", "idempotency_key", name="uq_generation_request"),
        CheckConstraint(
            "status IN ('queued','processing','succeeded','failed','cancelled')", name="job_status"
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="job_progress"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    recovery_count: Mapped[int] = mapped_column(default=0)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    model_key: Mapped[str | None] = mapped_column(String(255))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class QualityReport(Base):
    __tablename__ = "quality_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','pass','needs_review','failed','not_evaluated')",
            name="quality_status",
        ),
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="not_evaluated")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(String(3000), default="")
    uncertain_views: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewAudit(Base):
    """Append-only seller decisions for publication and revocation."""

    __tablename__ = "review_audits"
    __table_args__ = (
        CheckConstraint("decision IN ('approve','reject')", name="review_audit_decision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    seller_id: Mapped[str] = mapped_column(String(36), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TryOnJob(Base):
    """Private, user-owned try-on input and asynchronous processing state."""

    __tablename__ = "tryon_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_tryon_request"),
        CheckConstraint(
            "status IN ('queued','processing','needs_review','succeeded','failed','deleted')",
            name="tryon_status",
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="tryon_progress"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(32), default="diagnostic")
    framing: Mapped[str] = mapped_column(String(20))
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    no_training: Mapped[bool] = mapped_column(default=True)
    source_key: Mapped[str | None] = mapped_column(String(255))
    result_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(default=0)
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
