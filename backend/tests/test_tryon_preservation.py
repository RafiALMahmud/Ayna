from PIL import Image, ImageDraw

from app.modules.tryon.preservation import (
    build_preservation_plan,
    composite_original_resolution,
    local_contrast_energy,
    mask_pixels,
)


def labels(style: str) -> Image.Image:
    image = Image.new("L", (64, 96), 0)
    draw = ImageDraw.Draw(image)
    draw.ellipse((26, 3, 38, 17), fill=1)
    draw.rectangle((21, 18, 43, 68), fill=3)
    if style == "long":
        draw.rectangle((11, 20, 20, 73), fill=3)
        draw.rectangle((44, 20, 53, 73), fill=3)
    elif style == "short":
        draw.rectangle((11, 20, 20, 36), fill=3)
        draw.rectangle((44, 20, 53, 36), fill=3)
        draw.rectangle((13, 37, 18, 72), fill=12)
        draw.rectangle((46, 37, 51, 72), fill=12)
    elif style == "sleeveless":
        draw.rectangle((13, 20, 18, 72), fill=12)
        draw.rectangle((46, 20, 51, 72), fill=12)
    else:
        raise ValueError(style)
    draw.rectangle((13, 73, 18, 78), fill=13)
    draw.rectangle((46, 73, 51, 78), fill=13)
    draw.rectangle((21, 69, 43, 95), fill=6)
    return image


def source_image() -> Image.Image:
    image = Image.new("RGB", (128, 192), (236, 232, 224))
    draw = ImageDraw.Draw(image)
    draw.rectangle((42, 36, 86, 138), fill=(35, 55, 95))
    draw.rectangle((26, 74, 36, 145), fill=(174, 118, 86))
    draw.rectangle((92, 74, 102, 145), fill=(174, 118, 86))
    return image


def generated_with_marks() -> Image.Image:
    image = source_image().resize((64, 96), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    for y in range(38, 72, 4):
        draw.rectangle((13, y, 18, y + 1), fill=(20, 20, 20))
        draw.rectangle((46, y, 51, y + 1), fill=(20, 20, 20))
    return image


def test_original_resolution_and_visible_skin_are_preserved_exactly():
    source = source_image()
    generated = generated_with_marks()
    plan = build_preservation_plan(source, generated, labels("short"), labels("short"))
    result = composite_original_resolution(source, generated, plan)

    assert result.size == source.size
    for original, final, selected in zip(
        source.get_flattened_data(),
        result.get_flattened_data(),
        plan.preserve_mask.get_flattened_data(),
        strict=True,
    ):
        if selected:
            assert final == original


def test_newly_exposed_skin_is_low_frequency():
    source = source_image()
    generated = generated_with_marks()
    plan = build_preservation_plan(source, generated, labels("long"), labels("short"))
    result = composite_original_resolution(source, generated, plan)

    assert mask_pixels(plan.newly_exposed_skin) > 0
    assert local_contrast_energy(result, plan.newly_exposed_skin) < 3.0


def test_all_sleeve_transitions_build_expected_recovery_region():
    source = source_image()
    generated = generated_with_marks()
    cases = {
        ("long", "long"): False,
        ("short", "short"): False,
        ("long", "short"): True,
        ("short", "long"): False,
        ("long", "sleeveless"): True,
    }
    for (before, after), expected in cases.items():
        plan = build_preservation_plan(source, generated, labels(before), labels(after))
        assert bool(mask_pixels(plan.newly_exposed_skin)) is expected
