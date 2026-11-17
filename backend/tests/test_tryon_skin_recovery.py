from PIL import Image, ImageDraw

from app.modules.tryon.skin_recovery import (
    LABEL_ARMS,
    LABEL_FACE,
    LABEL_HANDS,
    LABEL_PANTS,
    LABEL_TOP,
    LABEL_TORSO,
    analyze_sleeves,
    build_skin_recovery_plan,
    mask_count,
)


def labels(style: str) -> Image.Image:
    image = Image.new("L", (64, 96), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((26, 4, 37, 16), fill=LABEL_FACE)
    draw.rectangle((29, 17, 34, 21), fill=LABEL_TORSO)
    draw.rectangle((20, 20, 43, 66), fill=LABEL_TOP)
    if style == "long":
        draw.rectangle((10, 22, 19, 72), fill=LABEL_TOP)
        draw.rectangle((44, 22, 53, 72), fill=LABEL_TOP)
    elif style == "short":
        draw.rectangle((10, 22, 19, 36), fill=LABEL_TOP)
        draw.rectangle((44, 22, 53, 36), fill=LABEL_TOP)
        draw.rectangle((12, 37, 18, 72), fill=LABEL_ARMS)
        draw.rectangle((45, 37, 51, 72), fill=LABEL_ARMS)
    elif style == "sleeveless":
        draw.rectangle((12, 22, 18, 72), fill=LABEL_ARMS)
        draw.rectangle((45, 22, 51, 72), fill=LABEL_ARMS)
    else:
        raise ValueError(style)
    draw.rectangle((12, 73, 18, 79), fill=LABEL_HANDS)
    draw.rectangle((45, 73, 51, 79), fill=LABEL_HANDS)
    draw.rectangle((20, 67, 43, 95), fill=LABEL_PANTS)
    return image


def test_long_to_short_expands_old_sleeve_without_touching_protected_regions():
    person = labels("long")
    plan = build_skin_recovery_plan(person, labels("short"))

    assert analyze_sleeves(person).style == "long"
    assert plan.sleeve_case == "long_to_short"
    assert plan.applied is True
    assert mask_count(plan.core_edit) > 0
    assert plan.edit_support.getpixel((15, 55)) == 255
    assert plan.edit_support.getpixel((15, 76)) == 0  # hand
    assert plan.edit_support.getpixel((32, 45)) == 0  # central garment
    assert plan.edit_support.getpixel((2, 45)) == 0  # background


def test_long_to_long_does_not_recover_skin():
    plan = build_skin_recovery_plan(labels("long"), labels("long"))
    assert plan.sleeve_case == "long_to_long"
    assert plan.applied is False
    assert mask_count(plan.edit_support) == 0


def test_short_to_short_does_not_recover_skin():
    plan = build_skin_recovery_plan(labels("short"), labels("short"))
    assert plan.sleeve_case == "short_to_short"
    assert plan.applied is False


def test_short_to_long_does_not_recover_skin():
    plan = build_skin_recovery_plan(labels("short"), labels("long"))
    assert plan.sleeve_case == "short_to_long"
    assert plan.applied is False


def test_sleeveless_target_recovers_more_of_long_sleeve_than_short_target():
    short_plan = build_skin_recovery_plan(labels("long"), labels("short"))
    sleeveless_plan = build_skin_recovery_plan(labels("long"), labels("sleeveless"))
    assert sleeveless_plan.sleeve_case == "long_to_sleeveless"
    assert sleeveless_plan.applied is True
    assert mask_count(sleeveless_plan.core_edit) > mask_count(short_plan.core_edit)
