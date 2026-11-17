import json

import pytest
from PIL import Image, ImageDraw

from eval.manifest import load_manifest
from eval.metrics import masked_l1, masked_ssim, metric_capabilities, new_marks_score
from eval.report import contact_sheet, side_by_side, write_results


def test_manifest_requires_consent_and_real_manifest_size(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "synthetic": True,
                "cases": [
                    {
                        "id": "x",
                        "person": "p",
                        "garment": "g",
                        "transition": "bare-arm",
                        "consent": False,
                    }
                ],
            }
        )
    )
    with pytest.raises(PermissionError):
        load_manifest(path, require_files=False)


def test_metrics_detect_changes():
    source = Image.new("RGB", (32, 32), "white")
    output = source.copy()
    ImageDraw.Draw(output).rectangle((8, 8, 15, 15), fill="black")
    mask = Image.new("L", source.size, 255)
    assert masked_l1(source, output, mask) > 0
    assert masked_ssim(source, source, mask) == pytest.approx(1)
    assert new_marks_score(source, output, mask) > 0
    assert metric_capabilities()["lpips"].startswith("unavailable")


def test_report_artifacts(tmp_path):
    left = Image.new("RGB", (24, 32), "white")
    right = Image.new("RGB", (24, 32), "navy")
    side_by_side(left, right, tmp_path / "case.png")
    contact_sheet([("case", left)], tmp_path / "worst10.png")
    write_results(
        tmp_path,
        [{"id": "case", "masked_l1": 0.0, "ssim": 1.0, "new_marks": 0.0}],
        metric_capabilities(),
    )
    assert {"case.png", "worst10.png", "metrics.json", "results.md"} <= {
        p.name for p in tmp_path.iterdir()
    }
