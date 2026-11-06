import io
import sys
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from app.common.config import Settings
from app.modules.quality.analysis import analyze_aligned_views
from app.modules.quality.opencv_alignment import AlignmentResult
from app.modules.quality.optional_models import (
    OptionalModelUnavailable,
    OptionalQualityRuntime,
    choose_device,
    load_dinov2_local,
    load_sam2_local,
    optional_quality_runtime,
    run_with_cpu_fallback,
)


def image(color: str, shape: str = "box") -> bytes:
    canvas = Image.new("RGB", (96, 96), "white")
    draw = ImageDraw.Draw(canvas)
    if shape == "box":
        draw.rectangle((20, 20, 76, 76), fill=color)
    else:
        draw.ellipse((32, 12, 64, 84), fill=color)
    output = io.BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()


def test_missing_camera_match_produces_no_fabricated_metrics():
    result = analyze_aligned_views({"front": image("red")}, {"back": image("red")})
    assert result.status == "not_evaluated"
    assert result.metrics == {}
    assert result.uncertain_views == ["back", "front"]


def test_aligned_identical_view_passes_interpretable_checks():
    front = image("#315f9b")
    result = analyze_aligned_views({"front": front}, {"front": front}, 128)
    assert result.status == "pass"
    assert result.metrics["aligned_views"] == ["front"]
    assert result.metrics["views"]["front"]["silhouette_iou"] == 1.0
    assert result.metrics["flags"] == []


def test_aligned_mismatch_is_flagged_for_human_review():
    def verified(_reference, render, _size):
        return AlignmentResult(
            accepted=True,
            aligned_render=render,
            diagnostics={"method": "test-calibration", "accepted": True},
            metrics={},
        )

    result = analyze_aligned_views(
        {"front": image("red", "box")},
        {"front": image("blue", "ellipse")},
        128,
        alignment_verifier=verified,
    )
    assert result.status == "needs_review"
    assert any("geometry" in flag for flag in result.metrics["flags"])
    assert any("color" in flag for flag in result.metrics["flags"])


def test_matching_label_without_alignment_evidence_produces_no_numbers():
    result = analyze_aligned_views(
        {"front": image("red", "box")},
        {"front": image("red", "ellipse")},
    )
    assert result.status == "not_evaluated"
    assert result.metrics == {}
    assert "camera alignment" in result.notes


def test_optional_runtime_is_cpu_safe_and_retries_cuda_oom(monkeypatch):
    assert choose_device("cpu") == "cpu"
    cuda = SimpleNamespace(is_available=lambda: True, empty_cache=lambda: None)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    calls = []

    def operation(device):
        calls.append(device)
        if device == "cuda":
            raise RuntimeError("CUDA out of memory")
        return "ok"

    assert run_with_cpu_fallback(operation, "auto") == ("ok", "cpu")
    assert calls == ["cuda", "cpu"]


def test_optional_features_are_disabled_and_lazy_by_default():
    disabled = Settings(quality_enable_sam2=False, quality_enable_dinov2=False)
    assert optional_quality_runtime(disabled) is None

    configured_but_not_loaded = Settings(
        quality_enable_dinov2=True,
        quality_dinov2_model_path="Z:/explicit/local/path/not-loaded-yet",
    )
    runtime = optional_quality_runtime(configured_but_not_loaded)
    assert runtime is not None and runtime.dinov2_scorer is not None


def test_mocked_sam2_refines_masks_only_after_alignment():
    calls = []

    def refiner(reference, render, reference_mask, render_mask, size):
        calls.append((reference, render, size))
        return reference_mask, render_mask, "cpu"

    runtime = OptionalQualityRuntime(sam2_refiner=refiner)
    unmatched = analyze_aligned_views(
        {"front": image("red")},
        {"back": image("red")},
        optional_runtime=runtime,
    )
    assert unmatched.status == "not_evaluated"
    assert calls == []

    front = image("red")
    aligned = analyze_aligned_views(
        {"front": front},
        {"front": front},
        128,
        optional_runtime=runtime,
    )
    assert len(calls) == 1
    assert aligned.metrics["views"]["front"]["sam2_mask_refined"] is True
    assert aligned.metrics["optional_models"]["sam2"] == {
        "status": "applied",
        "purpose": "foreground_mask_refinement",
        "applied_views": ["front"],
        "failed_views": {},
        "devices": ["cpu"],
    }


def test_mocked_dinov2_is_advisory_and_runs_only_for_aligned_views():
    calls = []

    def scorer(reference, render, size):
        calls.append((reference, render, size))
        return 0.81234, "cuda"

    runtime = OptionalQualityRuntime(dinov2_scorer=scorer)
    analyze_aligned_views(
        {"left": image("blue")},
        {"right": image("blue")},
        optional_runtime=runtime,
    )
    assert calls == []

    left = image("blue")
    result = analyze_aligned_views(
        {"left": left},
        {"left": left},
        128,
        optional_runtime=runtime,
    )
    assert len(calls) == 1
    assert result.metrics["views"]["left"]["dinov2_cosine_similarity"] == 0.8123
    dino = result.metrics["optional_models"]["dinov2"]
    assert dino["purpose"] == "advisory_aligned_view_correspondence"
    assert dino["identity_proof"] is False
    assert "not identity proof" in result.notes


def test_optional_model_failure_preserves_deterministic_baseline():
    front = image("#315f9b")
    baseline = analyze_aligned_views({"front": front}, {"front": front}, 128)

    def unavailable_refiner(*_args):
        raise ImportError("sam2 is intentionally absent")

    def unavailable_scorer(*_args):
        raise ImportError("transformers is intentionally absent")

    result = analyze_aligned_views(
        {"front": front},
        {"front": front},
        128,
        optional_runtime=OptionalQualityRuntime(unavailable_refiner, unavailable_scorer),
    )
    assert result.status == baseline.status == "pass"
    for metric in ("silhouette_iou", "mean_color_distance", "pixel_difference"):
        assert (
            result.metrics["views"]["front"][metric] == baseline.metrics["views"]["front"][metric]
        )
    assert result.metrics["views"]["front"]["sam2_mask_refined"] is False
    assert result.metrics["optional_models"]["sam2"]["status"] == "unavailable"
    assert result.metrics["optional_models"]["dinov2"]["status"] == "unavailable"
    assert "dinov2_cosine_similarity" not in result.metrics["views"]["front"]


def test_dinov2_loader_accepts_local_path_and_forbids_downloads(monkeypatch, tmp_path):
    model_path = tmp_path / "dinov2-small"
    model_path.mkdir()
    calls = []

    class Loader:
        @classmethod
        def from_pretrained(cls, path, **options):
            calls.append((cls.__name__, path, options))
            return FakeModel() if cls is ModelLoader else object()

    class ProcessorLoader(Loader):
        pass

    class ModelLoader(Loader):
        pass

    class FakeModel:
        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoImageProcessor=ProcessorLoader, AutoModel=ModelLoader),
    )
    load_dinov2_local(str(model_path), "cpu")

    assert len(calls) == 2
    assert all(call[1] == str(model_path.resolve()) for call in calls)
    assert all(call[2] == {"local_files_only": True, "trust_remote_code": False} for call in calls)
    with pytest.raises(OptionalModelUnavailable):
        load_dinov2_local("facebook/dinov2-small", "cpu")


def test_sam2_loader_requires_local_checkpoint_and_known_config(monkeypatch, tmp_path):
    checkpoint = tmp_path / "sam2.1_hiera_tiny.pt"
    checkpoint.write_bytes(b"mock checkpoint; never parsed")
    calls = []
    sam2_module = ModuleType("sam2")
    build_module = ModuleType("sam2.build_sam")

    def build_sam2(config, checkpoint_path, **options):
        calls.append((config, checkpoint_path, options))
        return object()

    build_module.build_sam2 = build_sam2
    monkeypatch.setitem(sys.modules, "sam2", sam2_module)
    monkeypatch.setitem(sys.modules, "sam2.build_sam", build_module)

    config = "configs/sam2.1/sam2.1_hiera_t.yaml"
    load_sam2_local(config, str(checkpoint), "cpu")
    assert calls == [
        (
            config,
            str(checkpoint.resolve()),
            {"device": "cpu", "apply_postprocessing": True},
        )
    ]
    with pytest.raises(OptionalModelUnavailable):
        load_sam2_local("https://example.invalid/config.yaml", str(checkpoint), "cpu")
