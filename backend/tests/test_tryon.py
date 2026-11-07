import io
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.common.config import get_settings
from app.common.db import SessionLocal
from app.common.models import Product, ProductImage, TryOnJob, now
from app.common.storage import get_storage
from app.main import app
from app.modules.tryon.tasks import process_tryon_job, purge_expired_tryons

ORIGIN = {"Origin": "http://localhost:5173"}


def register(client, prefix="tryon"):
    client.headers.update(ORIGIN)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex[:8]}@example.com",
            "name": "Try-on Customer",
            "password": "TestingPassword2026!",
            "role": "customer",
        },
    )
    assert response.status_code == 201
    return response.json()


def product(category="shirts"):
    with SessionLocal() as db:
        item = Product(
            seller_id=str(uuid4()),
            name="Try-on fixture",
            category=category,
            price_minor=10000,
            stock=2,
            sku=f"TRY-{uuid4().hex}",
            is_listed=True,
        )
        db.add(item)
        db.commit()
        return item.id


def photo(size=(600, 900)):
    output = io.BytesIO()
    Image.new("RGB", size, "navy").save(output, "JPEG")
    return output.getvalue()


def submit(client, product_id, **fields):
    data = {
        "framing": "full_body",
        "consent": "true",
        "no_training": "true",
        **fields,
    }
    return client.post(
        f"/api/v1/try-on/products/{product_id}/jobs",
        headers={"Idempotency-Key": f"tryon-{uuid4()}"},
        data=data,
        files={"photo": ("person.jpg", photo(), "image/jpeg")},
    )


def test_tryon_requires_account_supported_category_and_consent(client):
    pid = product("bags")
    assert submit(client, pid).status_code == 401
    register(client)
    response = submit(client, pid)
    assert response.status_code == 422
    assert "only for shirts" in response.json()["detail"]
    supported = product("shoes")
    assert submit(client, supported, consent="false").status_code == 422
    assert submit(client, supported, no_training="false").status_code == 422


def test_tryon_diagnostic_is_private_idempotent_and_deletable(client):
    user = register(client)
    pid = product("shirts")
    key = f"tryon-{uuid4()}"
    request = {
        "headers": {"Idempotency-Key": key},
        "data": {"framing": "upper_body", "consent": "true", "no_training": "true"},
        "files": {"photo": ("person.jpg", photo(), "image/jpeg")},
    }
    response = client.post(f"/api/v1/try-on/products/{pid}/jobs", **request)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["mode"] == "diagnostic"
    assert body["result_url"] is None
    assert body["diagnostics"]["result_generated"] is False
    assert "source" not in str(body).lower()

    duplicate = client.post(f"/api/v1/try-on/products/{pid}/jobs", **request)
    assert duplicate.json()["id"] == body["id"]
    with SessionLocal() as db:
        job = db.get(TryOnJob, body["id"])
        key_path = job.source_key
        assert job.user_id == user["id"]
        assert key_path and get_storage().get(key_path)

    other = TestClient(app, headers=ORIGIN)
    register(other, "other")
    assert other.get(f"/api/v1/try-on/jobs/{body['id']}").status_code == 404
    assert other.get(f"/api/v1/try-on/jobs/{body['id']}/result").status_code == 404

    deleted = client.delete(f"/api/v1/try-on/jobs/{body['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    with SessionLocal() as db:
        job = db.get(TryOnJob, body["id"])
        assert job.source_key is None and job.result_key is None


def test_tryon_rejects_unsuitable_framing_and_disabled_provider(client, monkeypatch):
    register(client)
    shoes = product("shoes")
    response = client.post(
        f"/api/v1/try-on/products/{shoes}/jobs",
        headers={"Idempotency-Key": f"tryon-{uuid4()}"},
        data={"framing": "full_body", "consent": "true", "no_training": "true"},
        files={"photo": ("landscape.jpg", photo((900, 600)), "image/jpeg")},
    )
    assert response.status_code == 422
    assert "portrait" in response.json()["detail"]
    monkeypatch.setattr(get_settings(), "tryon_provider", "disabled")
    assert submit(client, shoes).status_code == 503


def test_tryon_processing_failure_and_retention_cleanup(client):
    user = register(client)
    pid = product("pants")
    with SessionLocal() as db:
        missing = TryOnJob(
            user_id=user["id"],
            product_id=pid,
            idempotency_key=f"missing-{uuid4()}",
            provider="diagnostic",
            framing="full_body",
            consent_at=now(),
            no_training=True,
            source_key="tryon/missing.png",
            status="queued",
            progress=0,
            diagnostics={},
            expires_at=now() + timedelta(hours=1),
        )
        db.add(missing)
        db.commit()
        missing_id = missing.id
    process_tryon_job(missing_id)
    with SessionLocal() as db:
        assert db.get(TryOnJob, missing_id).status == "failed"

    response = submit(client, pid)
    job_id = response.json()["id"]
    with SessionLocal() as db:
        job = db.get(TryOnJob, job_id)
        job.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert purge_expired_tryons() == 1
    with SessionLocal() as db:
        assert db.get(TryOnJob, job_id).status == "deleted"


def test_deleted_job_cannot_be_recreated_by_late_local_result(client, monkeypatch):
    user = register(client)
    pid = product("shirts")
    source_key = f"tryon/{user['id']}/late-source.png"
    garment_key = f"products/{pid}/garment.png"
    get_storage().put(source_key, photo(), "image/png")
    get_storage().put(garment_key, photo(), "image/png")
    with SessionLocal() as db:
        db.add(
            ProductImage(
                product_id=pid,
                storage_key=garment_key,
                original_key=garment_key,
                view_tag="front",
                sort_order=0,
            )
        )
        job = TryOnJob(
            user_id=user["id"],
            product_id=pid,
            idempotency_key=f"late-{uuid4()}",
            provider="fashn_vton",
            framing="upper_body",
            consent_at=now(),
            no_training=True,
            source_key=source_key,
            status="queued",
            progress=0,
            diagnostics={},
            expires_at=now() + timedelta(hours=1),
        )
        db.add(job)
        db.commit()
        job_id = job.id

    def late_result(*_args, **_kwargs):
        with SessionLocal() as db:
            row = db.get(TryOnJob, job_id)
            row.status = "deleted"
            row.source_key = None
            row.deleted_at = now()
            db.commit()
        return photo(), {"elapsed_seconds": 1.0}

    monkeypatch.setattr("app.modules.tryon.tasks.infer", late_result)
    process_tryon_job(job_id)
    with SessionLocal() as db:
        row = db.get(TryOnJob, job_id)
        assert row.status == "deleted"
        assert row.result_key is None
