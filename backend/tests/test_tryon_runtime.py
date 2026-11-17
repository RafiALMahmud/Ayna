import io
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from app.common.db import SessionLocal
from app.common.models import Product, ProductImage, TryOnJob, now
from app.common.storage import get_storage
from app.modules.tryon.local_fashn import (
    TryOnInferenceError,
    _validate_result,
    infer,
    terminate_process_tree,
)
from app.modules.tryon.tasks import process_tryon_job


def image_bytes(fmt="PNG"):
    data = io.BytesIO()
    Image.new("RGB", (600, 900), "navy").save(data, fmt)
    return data.getvalue()


def fashn_job(category="shirts"):
    with SessionLocal() as db:
        product = Product(
            seller_id=str(uuid4()),
            name="Runtime shirt",
            category=category,
            price_minor=10000,
            stock=2,
            sku=f"RUNTIME-{uuid4().hex}",
            is_listed=True,
        )
        db.add(product)
        db.flush()
        garment_key = f"products/{product.id}/runtime.png"
        source_key = f"tryon/runtime/{uuid4()}/source.png"
        get_storage().put(garment_key, image_bytes(), "image/png")
        get_storage().put(source_key, image_bytes(), "image/png")
        db.add(
            ProductImage(
                product_id=product.id,
                storage_key=garment_key,
                original_key=garment_key,
                view_tag="front",
                sort_order=0,
            )
        )
        job = TryOnJob(
            user_id=str(uuid4()),
            product_id=product.id,
            idempotency_key=f"runtime-{uuid4()}",
            provider="fashn_vton",
            framing="full_body" if category == "dresses" else "upper_body",
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
        return job.id


def test_dress_uses_one_piece_fashn_category(monkeypatch):
    job_id = fashn_job("dresses")
    captured = {}

    def successful(_person, _garment, category, **_kwargs):
        captured["category"] = category
        return image_bytes(), {"elapsed_seconds": 1.0, "device": "cuda:0"}

    monkeypatch.setattr("app.modules.tryon.tasks.infer", successful)
    process_tryon_job(job_id)

    with SessionLocal() as db:
        job = db.get(TryOnJob, job_id)
        assert job.status == "succeeded"
    assert captured["category"] == "one-pieces"


def test_timeout_code_and_stage_diagnostics_are_preserved(monkeypatch):
    job_id = fashn_job()

    def timeout(*_args, stage_callback, **_kwargs):
        stage_callback(
            {
                "stage": "pose_detection",
                "event": "started",
                "elapsed_seconds": 3.0,
            }
        )
        raise TryOnInferenceError(
            "TRYON_TIMEOUT",
            {"tree_terminated": True, "cleanup_warning": "PermissionError"},
        )

    monkeypatch.setattr("app.modules.tryon.tasks.infer", timeout)
    process_tryon_job(job_id)

    with SessionLocal() as db:
        job = db.get(TryOnJob, job_id)
        assert job.status == "failed"
        assert job.progress == 100
        assert job.error_code == "TRYON_TIMEOUT"
        assert job.diagnostics["failed_stage"] == "pose_detection"
        assert job.diagnostics["tree_terminated"] is True
        assert job.diagnostics["cleanup_warning"] == "PermissionError"


def test_real_stage_events_are_persisted(monkeypatch):
    job_id = fashn_job()

    def staged(*_args, stage_callback, **_kwargs):
        stage_callback(
            {
                "stage": "process_startup",
                "event": "completed",
                "elapsed_seconds": 1.0,
                "metadata": {"torch_version": "test-torch", "cuda_available": True},
            }
        )
        stage_callback(
            {
                "stage": "model_loading",
                "event": "completed",
                "elapsed_seconds": 2.5,
                "metadata": {
                    "synthesis_device": "cuda",
                    "pose_providers": ["CPUExecutionProvider"],
                },
            }
        )
        stage_callback({"stage": "cuda_synthesis", "event": "started", "elapsed_seconds": 3.0})
        return image_bytes(), {"elapsed_seconds": 4.0, "device": "cuda:0"}

    monkeypatch.setattr("app.modules.tryon.tasks.infer", staged)
    process_tryon_job(job_id)

    with SessionLocal() as db:
        job = db.get(TryOnJob, job_id)
        assert job.status == "succeeded"
        assert job.progress == 100
        assert job.diagnostics["stage_timings"]["model_loading"] == 2.5
        assert job.diagnostics["runtime"]["synthesis_device"] == "cuda"
        assert job.diagnostics["runtime"]["pose_providers"] == ["CPUExecutionProvider"]
        assert job.diagnostics["runtime"]["torch_version"] == "test-torch"
        assert job.diagnostics["runtime"]["cuda_available"] is True


def test_timeout_cleanup_warning_does_not_mask_primary_error(tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    python.write_bytes(b"")
    source = tmp_path / "source"
    weights = tmp_path / "weights"
    source.mkdir()
    weights.mkdir()
    settings = SimpleNamespace(
        tryon_python=str(python),
        tryon_source_path=str(source),
        tryon_weights_path=str(weights),
        tryon_timeout_seconds=1,
        tryon_log_path=str(tmp_path / "logs"),
    )
    run_directory = tmp_path / "run"
    run_directory.mkdir()

    class Process:
        pid = 1234
        returncode = None

        def poll(self):
            return None

    ticks = iter((0.0, 2.0))
    monkeypatch.setattr("app.modules.tryon.local_fashn.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn.tempfile.mkdtemp",
        lambda **_kwargs: str(run_directory),
    )
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn.subprocess.Popen", lambda *_a, **_k: Process()
    )
    monkeypatch.setattr("app.modules.tryon.local_fashn.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn.terminate_process_tree",
        lambda _process: {"tree_terminated": True},
    )
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn._cleanup_directory", lambda _root: "PermissionError"
    )

    with pytest.raises(TryOnInferenceError) as raised:
        infer(image_bytes(), image_bytes(), "tops", cancelled=lambda: False, job_id="job")

    assert raised.value.code == "TRYON_TIMEOUT"
    assert raised.value.diagnostics["tree_terminated"] is True
    assert raised.value.diagnostics["cleanup_warning"] == "PermissionError"


def test_cancellation_terminates_process_tree_and_preserves_code(tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    python.write_bytes(b"")
    source = tmp_path / "source"
    weights = tmp_path / "weights"
    source.mkdir()
    weights.mkdir()
    settings = SimpleNamespace(
        tryon_python=str(python),
        tryon_source_path=str(source),
        tryon_weights_path=str(weights),
        tryon_timeout_seconds=900,
        tryon_log_path=str(tmp_path / "logs"),
    )

    class Process:
        pid = 2468

        def poll(self):
            return None

    terminated = []
    monkeypatch.setattr("app.modules.tryon.local_fashn.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn.subprocess.Popen", lambda *_a, **_k: Process()
    )
    monkeypatch.setattr(
        "app.modules.tryon.local_fashn.terminate_process_tree",
        lambda process: terminated.append(process.pid) or {"tree_terminated": True},
    )

    with pytest.raises(TryOnInferenceError) as raised:
        infer(image_bytes(), image_bytes(), "tops", cancelled=lambda: True, job_id="cancel")

    assert raised.value.code == "TRYON_CANCELLED"
    assert raised.value.diagnostics["tree_terminated"] is True
    assert terminated == [2468]


def test_windows_tree_termination_uses_taskkill_tree(monkeypatch):
    calls = []

    class Process:
        pid = 4321

        def poll(self):
            return None

        def wait(self, timeout):
            calls.append(("wait", timeout))

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.modules.tryon.local_fashn.WINDOWS", True)
    monkeypatch.setattr("app.modules.tryon.local_fashn.subprocess.run", run)
    diagnostics = terminate_process_tree(Process())

    assert calls[0][0] == ["taskkill", "/PID", "4321", "/T", "/F"]
    assert diagnostics["tree_terminated"] is True


def test_invalid_model_output_is_rejected(tmp_path):
    output = tmp_path / "result.png"
    output.write_bytes(b"not an image")
    with pytest.raises(TryOnInferenceError, match="TRYON_OUTPUT_INVALID"):
        _validate_result(output)
