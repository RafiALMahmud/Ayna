from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./.data/ayna.db"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: Literal["mock", "local_triposr", "meshy", "tripo"] = "mock"
    local_triposr_python: str | None = None
    local_triposr_source: str | None = None
    local_triposr_model_path: str | None = None
    local_triposr_timeout_seconds: int = Field(default=900, ge=60, le=3600)
    local_triposr_mc_resolution: int = Field(default=256, ge=128, le=320)
    ai_queue_max_jobs: int = Field(default=20, ge=1, le=500)
    meshy_api_key: str = ""
    meshy_daily_request_limit: int = Field(default=0, ge=0, le=100)
    generation_seller_daily_limit: int = Field(default=20, ge=1, le=100)
    generation_stale_seconds: int = Field(default=600, ge=60, le=7200)
    meshy_poll_seconds: int = Field(default=10, ge=1, le=30)
    meshy_timeout_seconds: int = Field(default=900, ge=30, le=1800)
    tripo_api_key: str = ""
    tripo_daily_request_limit: int = Field(default=0, ge=0, le=100)
    tripo_poll_seconds: int = Field(default=10, ge=1, le=30)
    tripo_timeout_seconds: int = Field(default=900, ge=30, le=1800)
    queue_mode: Literal["rq", "inline"] = "rq"
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = ".data/assets"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "ayna-local"
    s3_secret_key: str = "ayna-local-only-change-me"
    s3_bucket: str = "ayna-private"
    s3_region: str = "us-east-1"
    asset_signing_key: str = "ayna-local-signing-key-change-before-production"
    asset_ttl_seconds: int = Field(default=900, ge=30, le=3600)
    cors_origins: list[str] = ["http://localhost:5173"]
    dev_auth_enabled: bool = True
    max_image_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_image_pixels: int = Field(default=20_000_000, gt=0)
    max_images: int = Field(default=5, ge=2, le=5)
    min_images: int = Field(default=2, ge=2, le=5)
    currency: str = "BDT"
    storefront_url: str = "http://localhost:5173"
    session_days: int = Field(default=14, ge=1, le=30)
    demo_payments_enabled: bool = True
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Ayna <noreply@example.com>"
    smtp_starttls: bool = True
    quality_device: Literal["cpu", "auto", "cuda"] = "cpu"
    quality_max_image_size: int = Field(default=384, ge=128, le=1024)
    quality_enable_sam2: bool = False
    quality_enable_dinov2: bool = False
    quality_enable_opencv_alignment: bool = False
    quality_sam2_config: str | None = None
    quality_sam2_checkpoint: str | None = None
    quality_dinov2_model_path: str | None = None
    blender_optimization_enabled: bool = False
    blender_executable: str | None = None
    blender_timeout_seconds: int = Field(default=180, ge=30, le=900)
    blender_target_triangles: int = Field(default=20_000, ge=500, le=100_000)
    tryon_provider: Literal["disabled", "diagnostic", "fashn_vton"] = "diagnostic"
    tryon_python: str | None = None
    tryon_source_path: str | None = None
    tryon_weights_path: str | None = None
    tryon_timeout_seconds: int = Field(default=900, ge=60, le=3600)
    tryon_fashn_noncommercial_dependency_acknowledged: bool = False
    maintenance_interval_seconds: int = Field(default=60, ge=15, le=3600)
    tryon_retention_hours: int = Field(default=24, ge=1, le=168)
    tryon_max_image_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    @model_validator(mode="after")
    def guard_production(self) -> "Settings":
        if self.min_images > self.max_images:
            raise ValueError("min_images must not exceed max_images")
        if self.ai_provider == "meshy":
            if not self.meshy_api_key or not self.meshy_daily_request_limit:
                raise ValueError("Meshy requires a server key and a positive daily request cap")
            if self.queue_mode != "rq":
                raise ValueError("Hosted generation requires the background RQ worker")
        if self.ai_provider == "tripo":
            if not self.tripo_api_key or not self.tripo_daily_request_limit:
                raise ValueError("Tripo requires a server key and a positive daily request cap")
            if self.queue_mode != "rq":
                raise ValueError("Hosted generation requires the background RQ worker")
        if self.ai_provider == "local_triposr" and not all(
            (self.local_triposr_python, self.local_triposr_source, self.local_triposr_model_path)
        ):
            raise ValueError("Local TripoSR requires explicit Python, source, and weight paths")
        if self.tryon_provider == "fashn_vton" and not all(
            (self.tryon_python, self.tryon_source_path, self.tryon_weights_path)
        ):
            raise ValueError("FASHN VTON requires explicit Python, source, and weight paths")
        if (
            self.tryon_provider == "fashn_vton"
            and not self.tryon_fashn_noncommercial_dependency_acknowledged
        ):
            raise ValueError(
                "FASHN VTON depends on the noncommercial NVIDIA SegFormer parser; "
                "explicit demo-only acknowledgement is required"
            )
        if self.environment == "production":
            if self.demo_payments_enabled:
                raise ValueError("Demo payments are forbidden in production")
            if self.dev_auth_enabled or self.queue_mode == "inline":
                raise ValueError("Development auth and inline queue are forbidden in production")
            if self.asset_signing_key.startswith("ayna-local"):
                raise ValueError("Production requires a private asset signing key")
        if self.quality_enable_sam2 and (
            not self.quality_sam2_config or not self.quality_sam2_checkpoint
        ):
            raise ValueError("SAM 2 requires explicit local config and checkpoint paths")
        if self.quality_enable_dinov2 and not self.quality_dinov2_model_path:
            raise ValueError("DINOv2 requires an explicit local model path")
        if self.blender_optimization_enabled and not self.blender_executable:
            raise ValueError("Blender optimization requires an explicit local executable path")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
