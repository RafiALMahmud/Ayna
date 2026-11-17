"""Original-resolution preservation and low-frequency exposed-skin recovery."""

from dataclasses import dataclass
from math import pow
from statistics import median

from PIL import Image, ImageChops, ImageFilter

GARMENT_LABELS = (3, 4, 5, 6)
VISIBLE_SKIN_LABELS = (1, 12, 13)
PRESERVED_LABELS = (0, 1, 2, 12, 13)


@dataclass(frozen=True)
class PreservationPlan:
    garment_region: Image.Image
    preserve_mask: Image.Image
    preserve_support: Image.Image
    visible_skin: Image.Image
    newly_exposed_skin: Image.Image


def _binary(mask: Image.Image) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value else 0)


def _labels_mask(labels: Image.Image, ids: tuple[int, ...]) -> Image.Image:
    accepted = set(ids)
    return labels.convert("L").point([255 if value in accepted else 0 for value in range(256)])


def _odd(value: int) -> int:
    return value if value % 2 else value + 1


def _dilate(mask: Image.Image, pixels: int) -> Image.Image:
    return _binary(mask.filter(ImageFilter.MaxFilter(_odd(pixels * 2 + 1))))


def _erode(mask: Image.Image, pixels: int) -> Image.Image:
    return _binary(mask.filter(ImageFilter.MinFilter(_odd(pixels * 2 + 1))))


def _resize_labels(labels: Image.Image, size: tuple[int, int]) -> Image.Image:
    return labels.convert("L").resize(size, Image.Resampling.NEAREST)


def build_preservation_plan(
    input_image: Image.Image,
    generated_image: Image.Image,
    input_labels: Image.Image,
    output_labels: Image.Image,
    *,
    difference_threshold: int = 36,
    feather_pixels: int = 4,
) -> PreservationPlan:
    """Derive the garment edit and original-pixel preservation regions."""
    size = input_image.size
    generated = generated_image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    source = input_image.convert("RGB")
    source_labels = _resize_labels(input_labels, size)
    result_labels = _resize_labels(output_labels, size)

    output_garment = _labels_mask(result_labels, GARMENT_LABELS)
    difference = (
        ImageChops.difference(source, generated)
        .convert("L")
        .point(lambda value: 255 if value > difference_threshold else 0)
    )
    boundary_changes = ImageChops.multiply(difference, _dilate(output_garment, 8))
    garment_region = _binary(ImageChops.lighter(output_garment, boundary_changes))

    protected = _labels_mask(source_labels, PRESERVED_LABELS)
    preserve_support = _binary(ImageChops.multiply(protected, ImageChops.invert(garment_region)))
    preserve_mask = _erode(preserve_support, feather_pixels)
    visible_skin = _labels_mask(source_labels, VISIBLE_SKIN_LABELS)
    input_garment = _labels_mask(source_labels, GARMENT_LABELS)
    output_skin = _labels_mask(result_labels, (12,))
    newly_exposed = _binary(ImageChops.multiply(input_garment, output_skin))
    newly_exposed = _binary(
        ImageChops.multiply(newly_exposed, ImageChops.invert(_dilate(preserve_support, 1)))
    )
    return PreservationPlan(
        garment_region,
        preserve_mask,
        preserve_support,
        visible_skin,
        newly_exposed,
    )


def mask_pixels(mask: Image.Image) -> int:
    return mask.convert("L").histogram()[255]


def _srgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    values = []
    for channel in rgb:
        value = channel / 255.0
        values.append(value / 12.92 if value <= 0.04045 else pow((value + 0.055) / 1.055, 2.4))
    red, green, blue = values
    x = (red * 0.4124 + green * 0.3576 + blue * 0.1805) / 0.95047
    y = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z = (red * 0.0193 + green * 0.1192 + blue * 0.9505) / 1.08883

    def transform(value: float) -> float:
        return pow(value, 1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116

    fx, fy, fz = transform(x), transform(y), transform(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _lab_to_srgb(lab: tuple[float, float, float]) -> tuple[int, int, int]:
    lightness, a_value, b_value = lab
    fy = (lightness + 16) / 116
    fx = a_value / 500 + fy
    fz = fy - b_value / 200

    def inverse(value: float) -> float:
        cube = value**3
        return cube if cube > 0.008856 else (value - 16 / 116) / 7.787

    x, y, z = 0.95047 * inverse(fx), inverse(fy), 1.08883 * inverse(fz)
    linear = (
        x * 3.2406 + y * -1.5372 + z * -0.4986,
        x * -0.9689 + y * 1.8758 + z * 0.0415,
        x * 0.0557 + y * -0.2040 + z * 1.0570,
    )

    def encode(value: float) -> int:
        value = max(0.0, min(1.0, value))
        encoded = 12.92 * value if value <= 0.0031308 else 1.055 * pow(value, 1 / 2.4) - 0.055
        return round(encoded * 255)

    return tuple(encode(value) for value in linear)  # type: ignore[return-value]


def nearest_skin_lab(
    source: Image.Image, visible_skin: Image.Image, target: Image.Image
) -> tuple[float, float, float] | None:
    """Sample the nearest bounded set of visible-skin pixels in Lab space."""
    target_bounds = target.getbbox()
    if not target_bounds:
        return None
    center = ((target_bounds[0] + target_bounds[2]) / 2, (target_bounds[1] + target_bounds[3]) / 2)
    skin = visible_skin.convert("L")
    pixels = source.convert("RGB")
    candidates = []
    step = max(1, min(source.size) // 256)
    for y in range(0, source.height, step):
        for x in range(0, source.width, step):
            if skin.getpixel((x, y)):
                distance = (x - center[0]) ** 2 + (y - center[1]) ** 2
                candidates.append((distance, pixels.getpixel((x, y))))
    if not candidates:
        return None
    labs = [_srgb_to_lab(rgb) for _, rgb in sorted(candidates, key=lambda item: item[0])[:512]]
    return tuple(median(values) for values in zip(*labs, strict=True))  # type: ignore[return-value]


def smooth_new_skin(
    generated: Image.Image,
    source: Image.Image,
    visible_skin: Image.Image,
    newly_exposed: Image.Image,
) -> Image.Image:
    """Replace generated detail with a low-frequency nearest-skin Lab fill."""
    target_lab = nearest_skin_lab(source, visible_skin, newly_exposed)
    if target_lab is None or not newly_exposed.getbbox():
        return generated.convert("RGB")

    # Keep only broad illumination from the model.  A constant fill removes tattoos,
    # but also makes limbs look like flat cardboard; this blur is deliberately much
    # wider than tattoo/cloth texture while retaining cylindrical arm shading.
    low_frequency = generated.convert("RGB").filter(ImageFilter.GaussianBlur(8.0))
    selected = newly_exposed.convert("L")
    sampled_labs = [
        _srgb_to_lab(pixel)
        for pixel, keep in zip(
            low_frequency.get_flattened_data(),  # type: ignore[attr-defined]
            selected.get_flattened_data(),  # type: ignore[attr-defined]
            strict=True,
        )
        if keep
    ]
    if not sampled_labs:
        return generated.convert("RGB")
    current_center = tuple(median(values) for values in zip(*sampled_labs, strict=True))

    fill = low_frequency.copy()
    fill_pixels = fill.load()
    mask_pixels_data = selected.load()
    for y in range(fill.height):
        for x in range(fill.width):
            if not mask_pixels_data[x, y]:
                continue
            lab = _srgb_to_lab(fill_pixels[x, y])
            # Preserve subdued low-frequency light/shadow, but anchor chroma and
            # average lightness to the nearest genuine skin in the source image.
            corrected = (
                target_lab[0] + 0.75 * (lab[0] - current_center[0]),
                target_lab[1] + 0.35 * (lab[1] - current_center[1]),
                target_lab[2] + 0.35 * (lab[2] - current_center[2]),
            )
            fill_pixels[x, y] = _lab_to_srgb(corrected)
    result = generated.convert("RGB").copy()
    result.paste(fill, mask=selected)
    return result


def composite_original_resolution(
    source: Image.Image,
    generated: Image.Image,
    plan: PreservationPlan,
    *,
    recover_new_skin: bool = True,
    feather_pixels: int = 4,
) -> Image.Image:
    """Upscale generated pixels and restore protected original pixels at source resolution."""
    source = source.convert("RGB")
    result = generated.convert("RGB").resize(source.size, Image.Resampling.LANCZOS)
    if recover_new_skin and mask_pixels(plan.newly_exposed_skin):
        result = smooth_new_skin(result, source, plan.visible_skin, plan.newly_exposed_skin)
    feather = plan.preserve_support.filter(ImageFilter.GaussianBlur(feather_pixels))
    result = Image.composite(source, result, feather)
    result.paste(source, mask=plan.preserve_mask)
    return result


def local_contrast_energy(image: Image.Image, mask: Image.Image) -> float:
    """Mean high-frequency residual under a mask, used for synthetic regression checks."""
    gray = image.convert("L")
    low = gray.filter(ImageFilter.GaussianBlur(2.0))
    residual = ImageChops.difference(gray, low)
    # Exclude the garment/skin silhouette: that legitimate edge otherwise dominates
    # the score intended to detect marks inside skin.
    interior = _erode(mask.convert("L"), 3)
    values = [
        value
        for value, selected in zip(
            residual.get_flattened_data(),  # type: ignore[attr-defined]
            interior.get_flattened_data(),  # type: ignore[attr-defined]
            strict=True,
        )
        if selected
    ]
    return sum(values) / len(values) if values else 0.0
