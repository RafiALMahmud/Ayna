"""Sleeve-aware masks and bounded skin-tone recovery helpers.

The mask planner intentionally depends only on Pillow so its geometry can be unit tested in the
ordinary backend environment. NumPy/OpenCV are imported lazily only by the FASHN runtime helpers.
"""

from dataclasses import dataclass
from math import sqrt

from PIL import Image, ImageChops, ImageDraw, ImageFilter

LABEL_BACKGROUND = 0
LABEL_FACE = 1
LABEL_TOP = 3
LABEL_PANTS = 6
LABEL_ARMS = 12
LABEL_HANDS = 13
LABEL_LEGS = 14
LABEL_FEET = 15
LABEL_TORSO = 16


@dataclass(frozen=True)
class SleeveAnalysis:
    style: str
    exposure_ratio: float
    arm_pixels: int
    lateral_top_pixels: int


@dataclass(frozen=True)
class SkinRecoveryPlan:
    sleeve_case: str
    applied: bool
    source: SleeveAnalysis
    target: SleeveAnalysis
    arms: Image.Image
    hands: Image.Image
    neck: Image.Image
    skin_sample: Image.Image
    old_sleeve: Image.Image
    core_edit: Image.Image
    edit_support: Image.Image


def _labels(image: Image.Image) -> Image.Image:
    return image.convert("L")


def label_mask(labels: Image.Image, label_id: int) -> Image.Image:
    return _labels(labels).point([255 if value == label_id else 0 for value in range(256)])


def mask_count(mask: Image.Image) -> int:
    return mask.convert("L").histogram()[255]


def mask_or(*masks: Image.Image) -> Image.Image:
    result = Image.new("L", masks[0].size, 0)
    for mask in masks:
        result = ImageChops.lighter(result, mask.convert("L"))
    return result.point(lambda value: 255 if value else 0)


def mask_and(*masks: Image.Image) -> Image.Image:
    result = Image.new("L", masks[0].size, 255)
    for mask in masks:
        result = ImageChops.multiply(result, mask.convert("L"))
    return result.point(lambda value: 255 if value else 0)


def mask_not(mask: Image.Image) -> Image.Image:
    return ImageChops.invert(mask.convert("L"))


def _odd(value: int) -> int:
    value = max(1, value)
    return value if value % 2 else value + 1


def dilate(mask: Image.Image, size: int) -> Image.Image:
    return (
        mask.convert("L")
        .filter(ImageFilter.MaxFilter(_odd(size)))
        .point(lambda value: 255 if value else 0)
    )


def erode(mask: Image.Image, size: int) -> Image.Image:
    return (
        mask.convert("L")
        .filter(ImageFilter.MinFilter(_odd(size)))
        .point(lambda value: 255 if value else 0)
    )


def lateral_top_mask(labels: Image.Image) -> Image.Image:
    labels = _labels(labels)
    top = label_mask(labels, LABEL_TOP)
    bounds = top.getbbox()
    if not bounds:
        return Image.new("L", labels.size, 0)
    left, top_y, right, bottom = bounds
    face_bounds = label_mask(labels, LABEL_FACE).getbbox()
    center_x = (face_bounds[0] + face_bounds[2]) // 2 if face_bounds else (left + right) // 2
    core_half_width = max(1, int((right - left) * 0.28))
    lateral_region = Image.new("L", labels.size, 0)
    draw = ImageDraw.Draw(lateral_region)
    draw.rectangle((left, top_y, max(left, center_x - core_half_width), bottom), fill=255)
    draw.rectangle((min(right, center_x + core_half_width), top_y, right, bottom), fill=255)
    return mask_and(top, lateral_region)


def analyze_sleeves(labels: Image.Image) -> SleeveAnalysis:
    labels = _labels(labels)
    arms = label_mask(labels, LABEL_ARMS)
    lateral_top = lateral_top_mask(labels)
    arm_pixels = mask_count(arms)
    lateral_pixels = mask_count(lateral_top)
    exposure_ratio = arm_pixels / max(1, arm_pixels + lateral_pixels)
    top_bounds = label_mask(labels, LABEL_TOP).getbbox()
    arm_bounds = arms.getbbox()
    if exposure_ratio < 0.18:
        style = "long"
    elif (
        top_bounds
        and arm_bounds
        and ((arm_bounds[1] - top_bounds[1]) / max(1, top_bounds[3] - top_bounds[1]) < 0.15)
    ):
        style = "sleeveless"
    else:
        style = "short"
    return SleeveAnalysis(style, exposure_ratio, arm_pixels, lateral_pixels)


def build_skin_recovery_plan(
    person_labels: Image.Image,
    garment_labels: Image.Image,
) -> SkinRecoveryPlan:
    person_labels = _labels(person_labels)
    garment_labels = _labels(garment_labels)
    source = analyze_sleeves(person_labels)
    target = analyze_sleeves(garment_labels)
    sleeve_case = f"{source.style}_to_{target.style}"

    arms = label_mask(person_labels, LABEL_ARMS)
    hands = label_mask(person_labels, LABEL_HANDS)
    face = label_mask(person_labels, LABEL_FACE)
    torso = label_mask(person_labels, LABEL_TORSO)
    height = person_labels.height
    neck = mask_and(torso, dilate(face, max(3, int(height * 0.08))))
    skin_sample = mask_or(erode(face, max(3, int(height * 0.01))), neck)
    old_sleeve = lateral_top_mask(person_labels)
    empty = Image.new("L", person_labels.size, 0)

    if source.style != "long" or target.style not in {"short", "sleeveless"}:
        return SkinRecoveryPlan(
            sleeve_case,
            False,
            source,
            target,
            arms,
            hands,
            neck,
            skin_sample,
            old_sleeve,
            empty,
            empty.copy(),
        )

    bounds = old_sleeve.getbbox()
    if not bounds:
        return SkinRecoveryPlan(
            sleeve_case,
            False,
            source,
            target,
            arms,
            hands,
            neck,
            skin_sample,
            old_sleeve,
            empty,
            empty.copy(),
        )

    left, top_y, right, bottom = bounds
    sleeve_fraction = 0.38 if target.style == "short" else 0.08
    cutoff = top_y + int((bottom - top_y) * sleeve_fraction)
    lower_region = Image.new("L", person_labels.size, 0)
    ImageDraw.Draw(lower_region).rectangle((left, cutoff, right, bottom), fill=255)
    core_edit = mask_and(mask_or(old_sleeve, arms), lower_region)

    foreground = mask_not(label_mask(person_labels, LABEL_BACKGROUND))
    protected = mask_or(
        hands,
        face,
        neck,
        label_mask(person_labels, LABEL_PANTS),
        label_mask(person_labels, LABEL_LEGS),
        label_mask(person_labels, LABEL_FEET),
    )
    dilation_size = max(3, int(height * 0.012))
    edit_support = mask_and(dilate(core_edit, dilation_size), foreground, mask_not(protected))
    core_edit = mask_and(core_edit, edit_support)
    return SkinRecoveryPlan(
        sleeve_case,
        bool(mask_count(core_edit)),
        source,
        target,
        arms,
        hands,
        neck,
        skin_sample,
        old_sleeve,
        core_edit,
        edit_support,
    )


def resize_mask(mask: Image.Image, size: tuple[int, int]) -> Image.Image:
    return (
        mask.convert("L")
        .resize(size, Image.Resampling.NEAREST)
        .point(lambda value: 255 if value else 0)
    )


def fill_with_skin_sample(
    image: Image.Image,
    edit_support: Image.Image,
    skin_sample: Image.Image,
) -> tuple[Image.Image, tuple[int, int, int]]:
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    sample = np.asarray(resize_mask(skin_sample, image.size), dtype=np.uint8) > 0
    support = np.asarray(resize_mask(edit_support, image.size), dtype=np.uint8) > 0
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    target_lab = (
        np.median(lab[sample], axis=0) if np.any(sample) else np.median(lab.reshape(-1, 3), axis=0)
    ).astype(np.float32)
    source_luminance = cv2.bilateralFilter(lab[..., 0], 0, 24.0, 18.0)
    selected_luminance = source_luminance[support]
    center_luminance = (
        float(np.median(selected_luminance)) if selected_luminance.size else float(target_lab[0])
    )
    conditioned_lab = lab.copy()
    conditioned_lab[..., 0][support] = np.clip(
        target_lab[0] + 0.32 * (source_luminance[support] - center_luminance),
        0.0,
        100.0,
    )
    conditioned_lab[..., 1][support] = target_lab[1] + 0.12 * (lab[..., 1][support] - target_lab[1])
    conditioned_lab[..., 2][support] = target_lab[2] + 0.12 * (lab[..., 2][support] - target_lab[2])
    conditioned_rgb = np.clip(
        cv2.cvtColor(conditioned_lab, cv2.COLOR_LAB2RGB) * 255.0, 0, 255
    ).astype(np.uint8)
    conditioned = Image.fromarray(conditioned_rgb, "RGB")
    swatch = cv2.cvtColor(target_lab.reshape(1, 1, 3), cv2.COLOR_LAB2RGB)[0, 0]
    values = np.clip(swatch * 255.0, 0, 255)
    color = (int(values[0]), int(values[1]), int(values[2]))
    return conditioned, color


def _masked_lab_median(image: Image.Image, mask: Image.Image):
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    selected = np.asarray(resize_mask(mask, image.size), dtype=np.uint8) > 0
    if not np.any(selected):
        return None
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    return np.median(lab[selected], axis=0).astype(np.float32)


def skin_tone_delta(
    image: Image.Image,
    forearm_mask: Image.Image,
    reference_image: Image.Image,
    skin_sample_mask: Image.Image,
) -> float | None:
    forearm = _masked_lab_median(image, forearm_mask)
    reference = _masked_lab_median(reference_image, skin_sample_mask)
    if forearm is None or reference is None:
        return None
    return float(sqrt(sum(float(value) ** 2 for value in forearm - reference)))


def color_match_and_composite(
    baseline: Image.Image,
    recovered: Image.Image,
    core_edit: Image.Image,
    edit_support: Image.Image,
    reference_image: Image.Image,
    skin_sample_mask: Image.Image,
) -> tuple[Image.Image, dict[str, float | None]]:
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    baseline = baseline.convert("RGB")
    recovered = recovered.convert("RGB").resize(baseline.size, Image.Resampling.LANCZOS)
    support = resize_mask(edit_support, baseline.size)
    core = resize_mask(core_edit, baseline.size)
    reference_image = reference_image.convert("RGB").resize(baseline.size, Image.Resampling.LANCZOS)
    sample = resize_mask(skin_sample_mask, baseline.size)

    before_delta = skin_tone_delta(recovered, core, reference_image, sample)
    target_lab = _masked_lab_median(reference_image, sample)
    current_lab = _masked_lab_median(recovered, core)
    recovered_rgb = np.asarray(recovered, dtype=np.uint8)
    adjusted_rgb = recovered_rgb.copy()
    support_array = np.asarray(support, dtype=np.uint8) > 0
    smoothed_rgb = cv2.GaussianBlur(recovered_rgb, (0, 0), 2.4)
    adjusted_rgb[support_array] = np.clip(
        smoothed_rgb[support_array].astype(np.float32) * 0.72
        + recovered_rgb[support_array].astype(np.float32) * 0.28,
        0,
        255,
    ).astype(np.uint8)
    if target_lab is not None and current_lab is not None:
        delta = np.clip(target_lab - current_lab, [-20.0, -18.0, -18.0], [20.0, 18.0, 18.0])
        recovered_lab = cv2.cvtColor(adjusted_rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
        recovered_lab[support_array] += delta
        recovered_lab[..., 0][support_array] = target_lab[0] + np.clip(
            recovered_lab[..., 0][support_array] - target_lab[0], -18.0, 18.0
        )
        recovered_lab[..., 1][support_array] = target_lab[1] + 0.22 * (
            recovered_lab[..., 1][support_array] - current_lab[1]
        )
        recovered_lab[..., 2][support_array] = target_lab[2] + 0.22 * (
            recovered_lab[..., 2][support_array] - current_lab[2]
        )
        recovered_lab[..., 0] = np.clip(recovered_lab[..., 0], 0.0, 100.0)
        recovered_lab[..., 1:] = np.clip(recovered_lab[..., 1:], -127.0, 127.0)
        adjusted_rgb = np.clip(
            cv2.cvtColor(recovered_lab, cv2.COLOR_LAB2RGB) * 255.0, 0, 255
        ).astype(np.uint8)

    feather_radius = max(1.0, baseline.height * 0.006)
    feather = support.filter(ImageFilter.GaussianBlur(feather_radius))
    feather = ImageChops.multiply(feather, support)
    alpha = np.asarray(feather, dtype=np.float32) / 255.0
    base_rgb = np.asarray(baseline, dtype=np.uint8)
    composite = base_rgb.copy()
    support_pixels = np.asarray(support, dtype=np.uint8) > 0
    blended = (
        (
            adjusted_rgb.astype(np.float32) * alpha[..., None]
            + base_rgb.astype(np.float32) * (1.0 - alpha[..., None])
        )
        .round()
        .clip(0, 255)
        .astype(np.uint8)
    )
    composite[support_pixels] = blended[support_pixels]
    result = Image.fromarray(composite, "RGB")
    after_delta = skin_tone_delta(result, core, reference_image, sample)
    return result, {"skin_tone_delta_before": before_delta, "skin_tone_delta_after": after_delta}
