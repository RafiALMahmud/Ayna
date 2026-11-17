from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublishStatus(StrEnum):
    draft = "draft"
    generating = "generating"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class QualityStatus(StrEnum):
    pending = "pending"
    passed = "pass"
    needs_review = "needs_review"
    failed = "failed"
    not_evaluated = "not_evaluated"


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")
    category: str = Field(pattern="^(shoes|bags|shirts|pants|dresses)$")
    description: str = Field(default="", max_length=3000)


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    storage_key: str
    view_tag: str
    sort_order: int
    url: str


class ProductOut(BaseModel):
    id: UUID
    seller_id: UUID
    name: str
    category: str
    description: str
    images: list[ProductImageOut]
    created_at: datetime
    updated_at: datetime
    publish_status: PublishStatus


class ImagePlacement(BaseModel):
    id: UUID
    view_tag: Literal["front", "left", "right", "side", "back", "detail", "unspecified"]


class ImageOrderIn(BaseModel):
    images: list[ImagePlacement] = Field(min_length=1, max_length=5)


class JobOut(BaseModel):
    id: UUID
    product_id: UUID
    provider: str
    status: JobStatus
    progress: int
    created_at: datetime
    finished_at: datetime | None
    error_code: str | None
    model_asset_url: str | None
    preview_asset_urls: list[str]
    disclosure: str


class QualityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: UUID
    job_id: UUID
    status: QualityStatus
    metrics: dict
    notes: str
    uncertain_views: list[str]
    reviewed_by: UUID | None
    reviewed_at: datetime | None


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    notes: str = Field(default="", max_length=2000)


class PublicImage(BaseModel):
    id: UUID
    url: str
    view_tag: str


class PublicProduct(BaseModel):
    id: UUID
    name: str
    category: str
    description: str
    images: list[PublicImage]
    model_asset_url: str | None
    disclosure: str


class AppConfig(BaseModel):
    brand: str = "Ayna"
    provider: str
    min_images: int
    max_images: int
    max_image_bytes: int
    max_image_pixels: int
    dev_auth_enabled: bool
    seller_authenticated: bool = False


class HealthOut(BaseModel):
    status: str
    service: str = "Ayna API"


class ErrorOut(BaseModel):
    detail: str
    request_id: str
