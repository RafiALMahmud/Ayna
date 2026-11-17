"""Optional classical detail restoration constrained to the editable region."""

from PIL import Image, ImageChops, ImageFilter

from app.modules.tryon.preservation import PreservationPlan


def restore_edit_region(
    source: Image.Image,
    composite: Image.Image,
    plan: PreservationPlan,
    *,
    radius: float = 1.4,
    percent: int = 85,
    threshold: int = 5,
) -> Image.Image:
    """Sharpen garment/new skin while preserving protected pixels exactly."""
    source = source.convert("RGB")
    result = composite.convert("RGB").resize(source.size, Image.Resampling.LANCZOS)
    editable = ImageChops.lighter(plan.garment_region, plan.newly_exposed_skin)
    editable = ImageChops.multiply(editable, ImageChops.invert(plan.preserve_mask))
    sharpened = result.filter(ImageFilter.UnsharpMask(radius, percent, threshold))
    result = Image.composite(sharpened, result, editable.filter(ImageFilter.GaussianBlur(1)))
    result.paste(source, mask=plan.preserve_mask)
    return result
