"""Interpretable, CPU-safe image checks for defensibly aligned product views.

The engine deliberately refuses to compare differently labelled or unknown camera views.
It is not an identity verifier and its signals must remain advisory to the seller.
"""

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.quality.opencv_alignment import AlignmentResult
from app.modules.quality.optional_models import MaskPairRefiner, OptionalQualityRuntime

KNOWN_VIEWS = ("front", "left", "right", "side", "back")


@dataclass(frozen=True)
class AnalysisResult:
    status: str
    metrics: dict
    notes: str
    uncertain_views: list[str]


def _pixels(data: bytes, size: int) -> tuple[list[tuple[int, int, int]], int, int]:
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.fit(source.convert("RGB"), (size, size))
        flattened = getattr(image, "get_flattened_data", None)
        pixels = flattened() if flattened else image.getdata()
        return list(pixels), image.width, image.height


def _foreground(pixels: list[tuple[int, int, int]], width: int) -> list[bool]:
    corners = [pixels[0], pixels[width - 1], pixels[-width], pixels[-1]]
    background = tuple(sum(value[channel] for value in corners) / 4 for channel in range(3))
    return [max(abs(pixel[i] - background[i]) for i in range(3)) >= 28 for pixel in pixels]


def _mean_color(pixels: list[tuple[int, int, int]], mask: list[bool]) -> tuple[float, float, float]:
    selected = [pixel for pixel, keep in zip(pixels, mask, strict=True) if keep] or pixels
    channels = [sum(pixel[i] for pixel in selected) / len(selected) for i in range(3)]
    return channels[0], channels[1], channels[2]


def _signals(
    reference: bytes,
    render: bytes,
    size: int,
    mask_refiner: MaskPairRefiner | None = None,
) -> tuple[dict[str, float], str | None, str | None]:
    ref, width, _ = _pixels(reference, size)
    candidate, _, _ = _pixels(render, size)
    ref_mask = _foreground(ref, width)
    candidate_mask = _foreground(candidate, width)
    refinement_device: str | None = None
    refinement_error: str | None = None
    if mask_refiner is not None:
        try:
            refined_ref, refined_candidate, refinement_device = mask_refiner(
                reference,
                render,
                ref_mask,
                candidate_mask,
                size,
            )
            expected = size * size
            if (
                len(refined_ref) != expected
                or len(refined_candidate) != expected
                or not any(refined_ref)
                or not any(refined_candidate)
            ):
                raise ValueError("optional mask refinement returned invalid masks")
            ref_mask = [bool(value) for value in refined_ref]
            candidate_mask = [bool(value) for value in refined_candidate]
        except Exception as exc:
            refinement_device = None
            refinement_error = exc.__class__.__name__
    intersection = sum(a and b for a, b in zip(ref_mask, candidate_mask, strict=True))
    union = sum(a or b for a, b in zip(ref_mask, candidate_mask, strict=True))
    silhouette_iou = intersection / union if union else 1.0
    ref_color, candidate_color = _mean_color(ref, ref_mask), _mean_color(candidate, candidate_mask)
    color_distance = sum(abs(a - b) for a, b in zip(ref_color, candidate_color, strict=True)) / (
        3 * 255
    )
    pixel_difference = sum(
        sum(abs(a - b) for a, b in zip(left, right, strict=True))
        for left, right in zip(ref, candidate, strict=True)
    ) / (len(ref) * 3 * 255)
    return (
        {
            "silhouette_iou": round(silhouette_iou, 4),
            "mean_color_distance": round(color_distance, 4),
            "pixel_difference": round(pixel_difference, 4),
        },
        refinement_device,
        refinement_error,
    )


def _optional_summary(
    purpose: str,
    applied_views: list[str],
    failed_views: dict[str, str],
    devices: set[str],
) -> dict:
    if applied_views and failed_views:
        status = "partial"
    elif applied_views:
        status = "applied"
    else:
        status = "unavailable"
    return {
        "status": status,
        "purpose": purpose,
        "applied_views": sorted(applied_views),
        "failed_views": dict(sorted(failed_views.items())),
        "devices": sorted(devices),
    }


def analyze_aligned_views(
    references: dict[str, bytes],
    renders: dict[str, bytes],
    max_image_size: int = 384,
    optional_runtime: OptionalQualityRuntime | None = None,
    alignment_verifier: Callable[[bytes, bytes, int], AlignmentResult] | None = None,
) -> AnalysisResult:
    """Compare only views with explicit pixel identity or verified camera alignment."""
    matched = sorted(set(references) & set(renders) & set(KNOWN_VIEWS))
    uncertain = sorted(
        {view for view in references if view not in matched}
        | {view for view in renders if view not in matched}
    )
    if not matched:
        return AnalysisResult(
            status="not_evaluated",
            metrics={},
            notes=(
                "No reference/render camera views could be defensibly aligned; "
                "seller review required."
            ),
            uncertain_views=uncertain or ["all views - camera alignment unavailable"],
        )

    view_metrics: dict[str, dict] = {}
    flags: list[str] = []
    invalid: list[str] = []
    rejected_alignment: list[str] = []
    sam2_applied: list[str] = []
    sam2_failed: dict[str, str] = {}
    sam2_devices: set[str] = set()
    dinov2_applied: list[str] = []
    dinov2_failed: dict[str, str] = {}
    dinov2_devices: set[str] = set()
    size = max(128, min(max_image_size, 1024))
    for view in matched:
        reference, render = references[view], renders[view]
        if reference == render:
            alignment = AlignmentResult(
                True,
                render,
                {"method": "byte-identical", "accepted": True, "reason": "identical_input"},
                {},
            )
        elif alignment_verifier is None:
            rejected_alignment.append(f"{view} - camera alignment not established")
            continue
        else:
            try:
                alignment = alignment_verifier(reference, render, min(size, 512))
            except Exception as exc:
                rejected_alignment.append(
                    f"{view} - alignment unavailable ({exc.__class__.__name__})"
                )
                continue
        if not alignment.accepted or alignment.aligned_render is None:
            reason = alignment.diagnostics.get("reason", "ambiguous_camera_alignment")
            rejected_alignment.append(f"{view} - {reason}")
            continue
        aligned_render = alignment.aligned_render
        try:
            signals, sam2_device, sam2_error = _signals(
                reference,
                aligned_render,
                size,
                optional_runtime.sam2_refiner if optional_runtime else None,
            )
        except (UnidentifiedImageError, OSError, ValueError):
            invalid.append(view)
            continue
        if signals["silhouette_iou"] < 0.65:
            flags.append(f"{view}: likely geometry/silhouette mismatch")
        if signals["mean_color_distance"] > 0.18:
            flags.append(f"{view}: likely color mismatch")
        if signals["pixel_difference"] > 0.35:
            flags.append(f"{view}: possible texture/logo/detail mismatch")
        if alignment.metrics.get("opencv_texture_gradient_difference", 0) > 0.3:
            flags.append(f"{view}: localized texture/detail regions need inspection")
        if alignment.metrics.get("opencv_lighting_normalized_chroma_distance", 0) > 0.18:
            flags.append(f"{view}: lighting-normalized color mismatch")

        values: dict = {
            **signals,
            **alignment.metrics,
            "alignment": alignment.diagnostics,
        }
        if optional_runtime and optional_runtime.sam2_refiner:
            values["sam2_mask_refined"] = sam2_error is None
            if sam2_error is None and sam2_device:
                sam2_applied.append(view)
                sam2_devices.add(sam2_device)
            else:
                sam2_failed[view] = sam2_error or "OptionalModelUnavailable"

        if optional_runtime and optional_runtime.dinov2_scorer:
            try:
                similarity, device = optional_runtime.dinov2_scorer(reference, aligned_render, size)
                if not -1.0 <= similarity <= 1.0:
                    raise ValueError("DINOv2 cosine similarity is outside its valid range")
                values["dinov2_cosine_similarity"] = round(similarity, 4)
                dinov2_applied.append(view)
                dinov2_devices.add(device)
            except Exception as exc:
                dinov2_failed[view] = exc.__class__.__name__
        view_metrics[view] = values

    uncertain.extend(f"{view} - unreadable comparison image" for view in invalid)
    uncertain.extend(rejected_alignment)
    if not view_metrics:
        if rejected_alignment:
            return AnalysisResult(
                status="not_evaluated",
                metrics={},
                notes=(
                    "Matching direction labels did not establish camera alignment; "
                    "no numerical fidelity measurement was produced."
                ),
                uncertain_views=sorted(set(uncertain)),
            )
        return AnalysisResult(
            status="failed",
            metrics={},
            notes="Aligned comparison images could not be decoded; no fidelity score was produced.",
            uncertain_views=uncertain,
        )
    status = "pass" if not flags and not uncertain else "needs_review"
    metrics: dict = {
        "engine": "aligned-interpretable-v2",
        "aligned_views": list(view_metrics),
        "views": view_metrics,
        "flags": flags,
    }
    if optional_runtime:
        optional_metrics: dict[str, dict] = {}
        if optional_runtime.sam2_refiner:
            optional_metrics["sam2"] = _optional_summary(
                "foreground_mask_refinement",
                sam2_applied,
                sam2_failed,
                sam2_devices,
            )
        if optional_runtime.dinov2_scorer:
            dinov2_summary = _optional_summary(
                "advisory_aligned_view_correspondence",
                dinov2_applied,
                dinov2_failed,
                dinov2_devices,
            )
            dinov2_summary["identity_proof"] = False
            optional_metrics["dinov2"] = dinov2_summary
        metrics["optional_models"] = optional_metrics
    notes = (
        "Advisory checks run only after alignment evidence; they cannot certify product identity "
        "or unseen details. Localized regions indicate where a human should inspect logos/text, "
        "not that those details were recognized."
    )
    if optional_runtime and optional_runtime.dinov2_scorer:
        notes += " DINOv2 similarity is an advisory correspondence signal, not identity proof."
    return AnalysisResult(
        status=status,
        metrics=metrics,
        notes=notes,
        uncertain_views=uncertain,
    )
