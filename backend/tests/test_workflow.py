import hashlib
import io
import json
import struct
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy import select

from app.common.config import Settings, get_settings
from app.common.db import SessionLocal
from app.common.models import GenerationJob, Product, QualityReport, ReviewAudit
from app.common.storage import LocalStorage, get_storage
from app.modules.generation.providers import MockProvider, dummy_glb
from app.modules.generation.tasks import process_job

OTHER = {"X-Dev-Seller-Id": "22222222-2222-4222-8222-222222222222"}


def photo() -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (64, 64), "orange")
    exif = image.getexif()
    exif[270] = "private metadata"
    image.save(output, "PNG", exif=exif)
    return output.getvalue()


def create(client, owner, count=2):
    response = client.post(
        "/api/v1/products",
        headers=owner,
        json={
            "name": "Ayna test tote",
            "category": "bags",
            "description": "Original test fixture",
        },
    )
    assert response.status_code == 201
    product = response.json()
    if count:
        response = client.post(
            f"/api/v1/products/{product['id']}/images",
            headers=owner,
            files=[("files", ("../../private.png", photo(), "image/png"))] * count,
        )
        assert response.status_code == 201, response.text
        product = response.json()
    return product


def generate(client, owner, product, key="test-key"):
    response = client.post(
        f"/api/v1/products/{product['id']}/generation-jobs",
        headers={**owner, "Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    job = client.get(f"/api/v1/generation-jobs/{response.json()['id']}", headers=owner).json()
    return job


def test_health_readiness_and_safe_errors(client):
    assert client.get("/health").json() == {"status": "ok", "service": "Ayna API"}
    assert client.get("/ready").status_code == 200
    response = client.get("/api/v1/products")
    assert response.status_code == 401
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "traceback" not in response.text.lower()
    assert client.get("/api/v1/config").json()["provider"] == "mock"


@pytest.mark.parametrize("count", [2, 5])
def test_full_workflow_privacy_idempotency_and_revocation(client, owner, count):
    product = create(client, owner, count)
    product_id = product["id"]
    assert len(product["images"]) == count
    assert client.get("/api/v1/store/products").json() == []
    assert client.get(f"/api/v1/products/{product_id}", headers=OTHER).status_code == 404
    assert client.get("/api/v1/products", headers=OTHER).json() == []
    derivative = client.get(product["images"][0]["url"])
    assert derivative.status_code == 200
    assert not Image.open(io.BytesIO(derivative.content)).getexif()
    assert client.get(product["images"][0]["url"].replace("sig=", "sig=bad")).status_code == 403
    job = generate(client, owner, product)
    assert job["status"] == "succeeded" and job["progress"] == 100
    assert "Dummy" in job["disclosure"]
    assert client.get(job["model_asset_url"]).content[:4] == b"glTF"
    assert client.get(f"/api/v1/generation-jobs/{job['id']}", headers=OTHER).status_code == 404
    assert generate(client, owner, product)["id"] == job["id"]
    process_job(job["id"])
    with SessionLocal() as db:
        assert db.get(GenerationJob, job["id"]).status == "succeeded"
    report = client.get(f"/api/v1/products/{product_id}/quality", headers=owner).json()
    assert report["status"] == "not_evaluated" and report["metrics"] == {}
    assert report["uncertain_views"]
    review = f"/api/v1/products/{product_id}/review"
    assert client.post(review, headers=OTHER, json={"decision": "approve"}).status_code == 404
    assert client.get(f"/api/v1/store/products/{product_id}/model").status_code == 404
    assert client.post(review, headers=owner, json={"decision": "approve"}).status_code == 200
    public = client.get(f"/api/v1/store/products/{product_id}").json()
    assert "seller_id" not in public and "storage_key" not in str(public)
    assert client.get(public["model_asset_url"]).content == dummy_glb()
    assert client.get(public["images"][0]["url"]).status_code == 200
    assert len(client.get("/api/v1/store/products").json()) == 1
    assert client.post(review, headers=owner, json={"decision": "reject"}).status_code == 200
    assert client.get(public["model_asset_url"]).status_code == 404
    assert client.get(public["images"][0]["url"]).status_code == 404
    assert client.get("/api/v1/store/products").json() == []
    with SessionLocal() as db:
        audits = db.scalars(
            select(ReviewAudit)
            .where(ReviewAudit.product_id == product_id)
            .order_by(ReviewAudit.created_at)
        ).all()
        assert [audit.decision for audit in audits] == ["approve", "reject"]


def test_image_count_limits_and_pending_review(client, owner):
    product = create(client, owner, 1)
    path = f"/api/v1/products/{product['id']}"
    assert (
        client.post(
            path + "/generation-jobs", headers={**owner, "Idempotency-Key": "one-image"}
        ).status_code
        == 422
    )
    assert (
        client.post(path + "/review", headers=owner, json={"decision": "approve"}).status_code
        == 409
    )
    assert (
        client.post(
            path + "/images", headers=owner, files=[("files", ("x.png", photo(), "image/png"))] * 5
        ).status_code
        == 422
    )
    after = client.get(path, headers=owner).json()["images"]
    assert [i["id"] for i in after] == [i["id"] for i in product["images"]]


@pytest.mark.parametrize(
    "data,mime,expected",
    [
        (b"not an image", "image/png", 422),
        (b"<svg/>", "image/svg+xml", 415),
        (photo(), "image/jpeg", 415),
    ],
)
def test_malformed_and_mismatched_uploads_are_atomic(client, owner, data, mime, expected):
    product = create(client, owner, 0)
    path = f"/api/v1/products/{product['id']}"
    response = client.post(
        path + "/images",
        headers=owner,
        files=[
            ("files", ("valid.png", photo(), "image/png")),
            ("files", ("bad", data, mime)),
        ],
    )
    assert response.status_code == expected
    assert client.get(path, headers=owner).json()["images"] == []


def test_byte_and_pixel_limits(client, owner, monkeypatch):
    product = create(client, owner, 0)
    path = f"/api/v1/products/{product['id']}/images"
    monkeypatch.setattr(get_settings(), "max_image_bytes", 4)
    assert (
        client.post(
            path, headers=owner, files={"files": ("x.png", photo(), "image/png")}
        ).status_code
        == 413
    )
    monkeypatch.setattr(get_settings(), "max_image_bytes", 100000)
    monkeypatch.setattr(get_settings(), "max_image_pixels", 10)
    assert (
        client.post(
            path, headers=owner, files={"files": ("x.png", photo(), "image/png")}
        ).status_code
        == 413
    )


def test_generation_failure_is_sanitized(client, owner):
    product = create(client, owner)
    with patch.object(MockProvider, "generate", side_effect=RuntimeError("SECRET: do not expose")):
        job = generate(client, owner, product)
    assert job["status"] == "failed" and job["model_asset_url"] is None
    assert job["error_code"] == "GENERATION_FAILED" and "SECRET" not in str(job)
    assert client.get("/api/v1/store/products").json() == []


def test_queue_outage_does_not_leave_product_generating(client, owner, monkeypatch):
    product = create(client, owner)
    monkeypatch.setattr(get_settings(), "queue_mode", "rq")
    with patch("app.modules.generation.routes.queue", side_effect=OSError("private queue address")):
        response = client.post(
            f"/api/v1/products/{product['id']}/generation-jobs",
            headers={**owner, "Idempotency-Key": "outage"},
        )
    assert response.status_code == 503 and "private queue" not in response.text


def test_seller_can_cancel_queued_generation_and_revoke_publication(client, owner):
    product = create(client, owner)
    with SessionLocal() as db:
        row = db.get(Product, product["id"])
        assert row is not None
        row.publish_status = "generating"
        job = GenerationJob(
            product_id=row.id,
            idempotency_key="cancel-test",
            provider="local_triposr",
            status="queued",
        )
        db.add(job)
        db.commit()
        job_id = job.id

    response = client.delete(f"/api/v1/generation-jobs/{job_id}", headers=owner)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    with SessionLocal() as db:
        cancelled = db.get(GenerationJob, job_id)
        assert cancelled.error_code == "CANCELLED_BY_SELLER"
        assert cancelled.model_key is None


def test_late_local_generation_cannot_publish_after_cancellation(client, owner, monkeypatch):
    product = create(client, owner)
    with SessionLocal() as db:
        row = db.get(Product, product["id"])
        assert row is not None
        row.publish_status = "generating"
        job = GenerationJob(
            product_id=row.id,
            idempotency_key="late-cancel-test",
            provider="local_triposr",
            status="queued",
        )
        db.add(job)
        db.commit()
        job_id = job.id

    def late_result(_provider, _images):
        with SessionLocal() as db:
            row = db.get(GenerationJob, job_id)
            assert row is not None
            row.status = "cancelled"
            row.error_code = "CANCELLED_BY_SELLER"
            db.commit()
        return MockProvider().generate([])

    monkeypatch.setattr("app.modules.generation.tasks.LocalTripoSRProvider.generate", late_result)
    process_job(job_id)
    with SessionLocal() as db:
        row = db.get(GenerationJob, job_id)
        assert row is not None
        assert row.status == "cancelled"
        assert row.model_key is None
    assert (
        client.get(f"/api/v1/products/{product['id']}", headers=owner).json()["publish_status"]
        == "draft"
    )


def test_mock_glb_is_deterministic_and_valid():
    with patch("socket.socket", side_effect=AssertionError("No network permitted")):
        first = MockProvider().generate(["front", "side"]).glb
        second = MockProvider().generate(["other"]).glb
    assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
    magic, version, size = struct.unpack("<III", first[:12])
    assert magic == 0x46546C67 and version == 2 and size == len(first)
    json_size = struct.unpack("<I", first[12:16])[0]
    document = json.loads(first[20 : 20 + json_size])
    assert "DUMMY" in document["nodes"][0]["name"]
    assert document["extras"]["license"] == "CC0-1.0"


def test_missing_published_asset_returns_safe_fallback_status(client, owner):
    product = create(client, owner)
    generate(client, owner, product)
    path = f"/api/v1/products/{product['id']}/review"
    client.post(path, headers=owner, json={"decision": "approve"})
    public = client.get(f"/api/v1/store/products/{product['id']}").json()
    with patch.object(get_storage(), "get", side_effect=FileNotFoundError("private path")):
        response = client.get(public["model_asset_url"])
    assert response.status_code == 404 and "private path" not in response.text


def test_failed_quality_cannot_be_approved(client, owner):
    product = create(client, owner)
    job = generate(client, owner, product)
    with SessionLocal() as db:
        report = db.get(QualityReport, job["id"])
        report.status = "failed"
        db.commit()
    response = client.post(
        f"/api/v1/products/{product['id']}/review",
        headers=owner,
        json={"decision": "approve", "notes": "Looks fine"},
    )
    assert response.status_code == 409
    assert client.get("/api/v1/store/products").json() == []


def test_public_catalog_hides_approved_product_if_current_model_is_invalid(client, owner):
    product = create(client, owner)
    job = generate(client, owner, product)
    review = f"/api/v1/products/{product['id']}/review"
    assert client.post(review, headers=owner, json={"decision": "approve"}).status_code == 200
    with SessionLocal() as db:
        generated = db.get(GenerationJob, job["id"])
        generated.status = "failed"
        db.commit()
    assert client.get("/api/v1/store/products").json() == []
    assert client.get(f"/api/v1/store/products/{product['id']}").status_code == 404


def test_production_guards_and_local_path_safety(tmp_path):
    with pytest.raises(ValueError):
        Settings(environment="production", dev_auth_enabled=True)
    with pytest.raises(ValueError):
        Settings(ai_provider="meshy")
    with pytest.raises(ValueError, match="Local TripoSR requires"):
        Settings(ai_provider="local_triposr")
    with pytest.raises(ValueError, match="noncommercial NVIDIA"):
        Settings(
            tryon_provider="fashn_vton",
            tryon_python="python.exe",
            tryon_source_path="source",
            tryon_weights_path="weights",
        )
    configured = Settings(
        tryon_provider="fashn_vton",
        tryon_python="python.exe",
        tryon_source_path="source",
        tryon_weights_path="weights",
        tryon_fashn_noncommercial_dependency_acknowledged=True,
    )
    assert configured.tryon_provider == "fashn_vton"
    with pytest.raises(ValueError):
        LocalStorage(str(tmp_path)).get("../secret")


def test_auth_can_be_disabled(client, owner, monkeypatch):
    monkeypatch.setattr(get_settings(), "dev_auth_enabled", False)
    assert client.get("/api/v1/products", headers=owner).status_code == 503


def test_ready_reports_storage_outage(client):
    with patch.object(get_storage(), "ready", side_effect=OSError("private disk path")):
        response = client.get("/ready")
    assert response.status_code == 503 and "private disk" not in response.text


def test_openapi_contract_has_fixed_enums_and_routes(client):
    document = client.get("/openapi.json").json()
    assert document["info"]["title"] == "Ayna API"
    for resource in [
        "products",
        "products/{product_id}/images",
        "generation-jobs/{job_id}",
        "products/{product_id}/quality",
        "products/{product_id}/review",
        "store/products",
    ]:
        assert f"/api/v1/{resource}" in document["paths"]
    assert set(document["components"]["schemas"]["JobStatus"]["enum"]) == {
        "queued",
        "processing",
        "succeeded",
        "failed",
        "cancelled",
    }
