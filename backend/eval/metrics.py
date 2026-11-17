"""Dependency-light try-on preservation and skin-quality metrics."""

from math import sqrt
from statistics import fmean

from PIL import Image, ImageChops, ImageFilter, ImageStat


def _selected_values(image: Image.Image, mask: Image.Image) -> list[int]:
    return [
        value
        for value, selected in zip(
            image.convert("L").get_flattened_data(),  # type: ignore[attr-defined]
            mask.convert("L").get_flattened_data(),  # type: ignore[attr-defined]
            strict=True,
        )
        if selected
    ]


def masked_l1(a: Image.Image, b: Image.Image, mask: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    values = []
    for pixel, selected in zip(
        diff.get_flattened_data(),  # type: ignore[attr-defined]
        mask.convert("L").get_flattened_data(),  # type: ignore[attr-defined]
        strict=True,
    ):
        if selected:
            values.extend(pixel)
    return fmean(values) if values else 0.0


def masked_ssim(a: Image.Image, b: Image.Image, mask: Image.Image) -> float:
    left = _selected_values(a, mask)
    right = _selected_values(b, mask)
    if not left:
        return 1.0
    mean_a, mean_b = fmean(left), fmean(right)
    var_a = fmean((value - mean_a) ** 2 for value in left)
    var_b = fmean((value - mean_b) ** 2 for value in right)
    covariance = fmean((x - mean_a) * (y - mean_b) for x, y in zip(left, right, strict=True))
    c1, c2 = 6.5025, 58.5225
    return ((2 * mean_a * mean_b + c1) * (2 * covariance + c2)) / (
        (mean_a**2 + mean_b**2 + c1) * (var_a + var_b + c2)
    )


def new_marks_score(source: Image.Image, output: Image.Image, skin_mask: Image.Image) -> float:
    def energy(image: Image.Image) -> float:
        gray = image.convert("L")
        residual = ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(2)))
        values = _selected_values(residual, skin_mask)
        return fmean(values) if values else 0.0

    return max(0.0, energy(output) - energy(source))


def skin_tone_delta(image: Image.Image, forearm: Image.Image, face: Image.Image) -> float | None:
    def mean_rgb(mask: Image.Image) -> tuple[float, float, float] | None:
        count = ImageStat.Stat(mask.convert("L")).sum[0] / 255
        if not count:
            return None
        stat = ImageStat.Stat(image.convert("RGB"), mask=mask.convert("L"))
        return tuple(stat.mean)  # type: ignore[return-value]

    arm, head = mean_rgb(forearm), mean_rgb(face)
    if arm is None or head is None:
        return None
    return sqrt(sum((x - y) ** 2 for x, y in zip(arm, head, strict=True)))


def metric_capabilities() -> dict[str, str]:
    return {
        "masked_l1": "available",
        "ssim": "available_dependency_light_global_window",
        "skin_tone_delta": "available_rgb_proxy",
        "new_marks": "available",
        "lpips": "unavailable_missing_lpips_package",
        "kid": "unavailable_missing_licensed_feature_extractor",
        "face_identity": "unavailable_missing_identity_model",
    }
