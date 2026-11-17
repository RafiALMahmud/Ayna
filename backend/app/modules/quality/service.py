from dataclasses import dataclass

from app.common.config import get_settings
from app.common.models import GenerationJob, Product, QualityReport
from app.modules.quality.analysis import AnalysisResult, analyze_aligned_views
from app.modules.quality.opencv_alignment import align_with_opencv
from app.modules.quality.optional_models import optional_quality_runtime
from app.modules.quality.rendering import (
    BatchRenderer,
    RenderBatch,
    render_glb_views,
)


@dataclass(frozen=True)
class QualityArtifacts:
    """A persisted report plus private, camera-labelled inspection renders."""

    report: QualityReport
    rendered_views: dict[str, bytes]
    render_metadata: dict


def _report(product: Product, job: GenerationJob, result: AnalysisResult) -> QualityReport:
    return QualityReport(
        product_id=product.id,
        job_id=job.id,
        status=result.status,
        metrics=result.metrics,
        notes=result.notes,
        uncertain_views=result.uncertain_views,
    )


def _render_unavailable(product: Product, job: GenerationJob, reason: str) -> QualityArtifacts:
    metadata = {"status": "unavailable", "reason": reason}
    result = AnalysisResult(
        status="not_evaluated",
        metrics={"rendering": metadata},
        notes=(
            "Deterministic GLB inspection renders were unavailable; no visual correspondence "
            "score was produced. Seller review is required."
        ),
        uncertain_views=["all views - GLB rendering unavailable"],
    )
    return QualityArtifacts(_report(product, job, result), {}, metadata)


def build_quality_artifacts(
    product: Product,
    job: GenerationJob,
    reference_images: dict[str, bytes] | None = None,
    rendered_views: dict[str, bytes] | None = None,
    *,
    model_glb: bytes | None = None,
    renderer: BatchRenderer | None = render_glb_views,
    evaluate_rendered_views: bool = True,
) -> QualityArtifacts:
    """Build a quality report without allowing rendering failures to fail generation.

    Callers must supply seller photographs keyed by defensible camera labels. Rendering a
    model does not establish correspondence by itself. The mock provider sets
    ``evaluate_rendered_views=False`` so its dummy geometry stays ``not_evaluated``.
    """
    batch: RenderBatch | None = None
    if rendered_views is None and model_glb is not None:
        if renderer is None:
            return _render_unavailable(product, job, "renderer is not configured")
        try:
            batch = renderer(model_glb, get_settings().quality_max_image_size)
            rendered_views = batch.images
        except Exception as exc:
            return _render_unavailable(product, job, str(exc) or exc.__class__.__name__)

    if batch is not None and not evaluate_rendered_views:
        failed = [f"{view} - render failed" for view in sorted(batch.failures)]
        uncertain = [
            *(f"{view} - mock geometry is not a product reconstruction" for view in batch.images),
            *failed,
        ]
        result = AnalysisResult(
            status="not_evaluated",
            # Preserve the established mock report contract; render metadata lives in
            # QualityArtifacts and job provenance rather than masquerading as a score.
            metrics={},
            notes=(
                "Deterministic inspection views were rendered from the dummy mock GLB, but "
                "mock geometry is unrelated to seller photographs. No fidelity score was produced."
            ),
            uncertain_views=sorted(uncertain),
        )
        return QualityArtifacts(_report(product, job, result), batch.images, batch.metadata)

    settings = get_settings()
    result = analyze_aligned_views(
        reference_images or {},
        rendered_views or {},
        settings.quality_max_image_size,
        optional_runtime=optional_quality_runtime(settings),
        alignment_verifier=(
            align_with_opencv if settings.quality_enable_opencv_alignment else None
        ),
    )
    metadata = batch.metadata if batch else {}
    if batch:
        metrics = dict(result.metrics)
        metrics["rendering"] = metadata
        uncertain = sorted(
            set(result.uncertain_views)
            | {f"{view} - deterministic render failed" for view in batch.failures}
        )
        status = "needs_review" if batch.failures and result.status == "pass" else result.status
        result = AnalysisResult(status, metrics, result.notes, uncertain)
    return QualityArtifacts(
        _report(product, job, result),
        dict(rendered_views or {}),
        metadata,
    )


def build_quality_report(
    product: Product,
    job: GenerationJob,
    reference_images: dict[str, bytes] | None = None,
    rendered_views: dict[str, bytes] | None = None,
) -> QualityReport:
    """Backward-compatible report-only entry point for already rendered image pairs."""
    return build_quality_artifacts(
        product,
        job,
        reference_images=reference_images,
        rendered_views=rendered_views,
    ).report
