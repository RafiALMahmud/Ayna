from PIL import Image, ImageDraw

from app.modules.tryon.preservation import PreservationPlan
from app.modules.tryon.restoration import restore_edit_region


def test_restoration_is_original_resolution_and_preserves_protected_pixels():
    source = Image.new("RGB", (80, 120), "#ddd8d0")
    composite = source.resize((40, 60))
    ImageDraw.Draw(composite).rectangle((10, 15, 30, 45), fill="#334477")
    garment = Image.new("L", source.size, 0)
    ImageDraw.Draw(garment).rectangle((20, 30, 60, 90), fill=255)
    preserve = Image.new("L", source.size, 255)
    ImageDraw.Draw(preserve).rectangle((20, 30, 60, 90), fill=0)
    empty = Image.new("L", source.size)
    plan = PreservationPlan(garment, preserve, preserve, empty, empty)

    result = restore_edit_region(source, composite, plan)

    assert result.size == source.size
    for before, after, selected in zip(
        source.get_flattened_data(),
        result.get_flattened_data(),
        preserve.get_flattened_data(),
        strict=True,
    ):
        if selected:
            assert after == before
