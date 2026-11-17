import pytest

from app.common.models import GenerationJob, Product
from app.modules.generation.providers import dummy_glb
from app.modules.quality.rendering import (
    GlbRenderError,
    ViewRenderError,
    render_glb_views,
    render_view_png,
)
from app.modules.quality.service import build_quality_artifacts


def product_and_job() -> tuple[Product, GenerationJob]:
    product = Product(
        id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        seller_id="11111111-1111-4111-8111-111111111111",
        name="Inspection fixture",
        category="bags",
        description="",
    )
    job = GenerationJob(
        id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        product_id=product.id,
        idempotency_key="quality-render-test",
        provider="mock",
    )
    return product, job


def test_cpu_renderer_produces_deterministic_labelled_png_metadata():
    first = render_glb_views(dummy_glb(), 128)
    second = render_glb_views(dummy_glb(), 128)

    assert set(first.images) == {"front", "left", "right", "back"}
    assert first.images == second.images
    assert first.failures == {}
    assert first.metadata["status"] == "complete"
    assert first.metadata["renderer"] == "ayna-cpu-raster-v2"
    assert first.metadata["deterministic"] is True
    assert first.metadata["image_size"] == 128
    assert first.metadata["triangle_count"] == 8
    assert first.metadata["views"]["front"]["camera_position"] == [0.0, 0.0, 1.0]
    assert all(image.startswith(b"\x89PNG\r\n\x1a\n") for image in first.images.values())


def test_missing_renderer_returns_not_evaluated_without_confidence():
    product, job = product_and_job()
    artifacts = build_quality_artifacts(product, job, model_glb=dummy_glb(), renderer=None)

    assert artifacts.report.status == "not_evaluated"
    assert artifacts.report.metrics == {
        "rendering": {"status": "unavailable", "reason": "renderer is not configured"}
    }
    assert artifacts.rendered_views == {}
    assert "no visual correspondence score" in artifacts.report.notes.lower()


def test_invalid_glb_isolated_as_not_evaluated():
    with pytest.raises(GlbRenderError, match="GLB"):
        render_glb_views(b"not-a-glb", 128)

    product, job = product_and_job()
    artifacts = build_quality_artifacts(product, job, model_glb=b"not-a-glb")
    assert artifacts.report.status == "not_evaluated"
    assert artifacts.rendered_views == {}
    assert artifacts.report.metrics["rendering"]["status"] == "unavailable"
    assert "all views - GLB rendering unavailable" in artifacts.report.uncertain_views


def test_partial_view_failure_keeps_only_defensibly_aligned_scores():
    def partial_renderer(mesh, view: str, image_size: int) -> bytes:
        if view in {"left", "back"}:
            raise ViewRenderError("simulated camera failure")
        return render_view_png(mesh, view, image_size)

    batch = render_glb_views(dummy_glb(), 128, view_renderer=partial_renderer)
    assert set(batch.images) == {"front", "right"}
    assert set(batch.failures) == {"left", "back"}
    assert batch.metadata["status"] == "partial"

    product, job = product_and_job()
    artifacts = build_quality_artifacts(
        product,
        job,
        reference_images={"front": batch.images["front"]},
        model_glb=dummy_glb(),
        renderer=lambda _data, _size: batch,
    )

    assert artifacts.report.status == "needs_review"
    assert artifacts.report.metrics["aligned_views"] == ["front"]
    assert set(artifacts.report.metrics["views"]) == {"front"}
    assert artifacts.report.metrics["rendering"]["failed_views"] == batch.failures
    assert "left - deterministic render failed" in artifacts.report.uncertain_views
    assert "back - deterministic render failed" in artifacts.report.uncertain_views


def test_mock_rendering_preserves_not_evaluated_behavior():
    product, job = product_and_job()
    artifacts = build_quality_artifacts(
        product,
        job,
        model_glb=dummy_glb(),
        evaluate_rendered_views=False,
    )

    assert artifacts.report.status == "not_evaluated"
    assert artifacts.report.metrics == {}
    assert artifacts.render_metadata["status"] == "complete"
    assert set(artifacts.rendered_views) == {"front", "left", "right", "back"}
    assert "no fidelity score" in artifacts.report.notes.lower()
