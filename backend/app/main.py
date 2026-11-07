import logging
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.config import get_settings
from app.common.db import get_db
from app.common.identity import optional_user
from app.common.models import GenerationJob, Product, ProductImage
from app.common.schemas import AppConfig, ErrorOut, HealthOut
from app.common.storage import get_storage, verify_asset
from app.modules.catalog.routes import router as catalog
from app.modules.commerce import accounts, admin, orders, payments
from app.modules.commerce import catalog as shop_catalog
from app.modules.generation.routes import router as generation
from app.modules.public_catalog.routes import router as public_catalog
from app.modules.quality.routes import router as quality
from app.modules.tryon.routes import router as tryon

settings = get_settings()
app = FastAPI(
    title="Ayna API",
    version="0.1.0",
    responses={
        code: {"model": ErrorOut}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 502, 503)
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_credentials=True,
    allow_headers=["Content-Type", "X-Dev-Seller-Id", "Idempotency-Key", "Authorization"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    error_headers = {
        "X-Request-ID": request.state.request_id,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "Origin is not allowed", "request_id": request.state.request_id},
                headers=error_headers,
            )
        if (
            (request.cookies.get("ayna_session") or request.cookies.get("ayna_guest_cart"))
            and not origin
            and not request.headers.get("authorization")
        ):
            if request.url.path != "/api/v1/payments/stripe/webhook":
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "An allowed Origin is required",
                        "request_id": request.state.request_id,
                    },
                    headers=error_headers,
                )
    try:
        response = await call_next(request)
    except Exception:
        logging.getLogger(__name__).exception("Request failed: %s", request.state.request_id)
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "An internal error occurred",
                "request_id": request.state.request_id,
            },
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail), "request_id": request.state.request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "request_id": request.state.request_id},
    )


@app.get("/health", response_model=HealthOut)
@app.get("/api/v1/health", response_model=HealthOut)
def health():
    return HealthOut(status="ok")


@app.get("/ready", response_model=HealthOut)
@app.get("/api/v1/ready", response_model=HealthOut)
def ready(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        if settings.queue_mode == "rq":
            Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        get_storage().ready()
    except Exception as exc:
        raise HTTPException(503, "A required service is unavailable") from exc
    return HealthOut(status="ready")


@app.get("/api/v1/config", response_model=AppConfig)
def config(user=Depends(optional_user)):
    return AppConfig(
        provider=settings.ai_provider,
        min_images=settings.min_images,
        max_images=settings.max_images,
        max_image_bytes=settings.max_image_bytes,
        max_image_pixels=settings.max_image_pixels,
        dev_auth_enabled=settings.dev_auth_enabled,
        seller_authenticated=bool(user and user.role in {"seller", "admin"}),
    )


@app.get("/api/v1/assets/{kind}/{asset_id}")
def private_asset(
    kind: str, asset_id: UUID, owner: UUID, expires: int, sig: str, db=Depends(get_db)
):
    if not verify_asset(kind, str(asset_id), str(owner), expires, sig):
        raise HTTPException(403, "Asset link is invalid or expired")
    if kind == "image":
        resource = db.get(ProductImage, str(asset_id))
        key = resource.storage_key if resource else None
        media_type = "image/png"
    elif kind == "model":
        resource = db.get(GenerationJob, str(asset_id))
        key = resource.model_key if resource and resource.status == "succeeded" else None
        media_type = "model/gltf-binary"
    elif kind in {"render-front", "render-left", "render-right", "render-back"}:
        resource = db.get(GenerationJob, str(asset_id))
        key = (
            resource.provenance.get("quality_render_keys", {}).get(kind[7:])
            if resource and resource.status == "succeeded"
            else None
        )
        media_type = "image/png"
    else:
        raise HTTPException(404, "Asset not found")
    product = db.get(Product, resource.product_id) if resource else None
    if key is None or product is None or product.seller_id != str(owner):
        raise HTTPException(404, "Asset not found")
    try:
        return Response(get_storage().get(key), media_type=media_type)
    except Exception as exc:
        raise HTTPException(404, "Asset unavailable") from exc


for router in (
    catalog,
    generation,
    quality,
    public_catalog,
    accounts.router,
    shop_catalog.router,
    orders.router,
    admin.router,
    payments.router,
    tryon,
):
    app.include_router(router, prefix="/api/v1")
