"""Opt-in RTX integration coverage for sleeve-aware skin recovery."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.modules.tryon.preservation import local_contrast_energy


@pytest.mark.skipif(
    os.getenv("AYNA_RUN_FASHN_GPU_TEST") != "1",
    reason="requires authorized private inputs, local weights, and CUDA",
)
def test_skin_recovery_runs_on_cuda_with_valid_output(tmp_path: Path):
    required = {
        name: os.environ.get(name)
        for name in (
            "TRYON_PYTHON",
            "TRYON_WEIGHTS_PATH",
            "AYNA_TRYON_TEST_PERSON",
            "AYNA_TRYON_TEST_GARMENT",
        )
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"missing opt-in environment: {', '.join(missing)}")

    runner = Path(__file__).resolve().parents[2] / "scripts" / "local_fashn_vton.py"
    output = tmp_path / "result.png"
    completed = subprocess.run(
        [
            required["TRYON_PYTHON"],
            str(runner),
            "--weights",
            required["TRYON_WEIGHTS_PATH"],
            "--person",
            required["AYNA_TRYON_TEST_PERSON"],
            "--garment",
            required["AYNA_TRYON_TEST_GARMENT"],
            "--category",
            "tops",
            "--output",
            str(output),
            "--skin-recovery",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    runtime = json.loads(completed.stdout.splitlines()[-1])
    assert runtime["device"] == "cuda:0"
    assert runtime["skin_recovery_applied"] is True
    assert runtime["peak_cuda_mib"] < 6144
    with Image.open(output) as image:
        image.verify()
        assert image.format == "PNG"


@pytest.mark.skipif(
    os.getenv("AYNA_RUN_FASHN_GPU_TEST") != "1",
    reason="requires authorized private tattoo-regression inputs, local weights, and CUDA",
)
def test_visible_skin_does_not_gain_generated_marks(tmp_path: Path):
    required = {
        name: os.environ.get(name)
        for name in (
            "TRYON_PYTHON",
            "TRYON_WEIGHTS_PATH",
            "AYNA_TRYON_TATTOO_PERSON",
            "AYNA_TRYON_TATTOO_GARMENT",
        )
    }
    missing = [name for name, value in required.items() if not value or not Path(value).is_file()]
    if missing:
        pytest.skip(f"missing opt-in tattoo fixture environment: {', '.join(missing)}")

    runner = Path(__file__).resolve().parents[2] / "scripts" / "local_fashn_vton.py"
    output = tmp_path / "result.png"
    debug = tmp_path / "debug"
    subprocess.run(
        [
            required["TRYON_PYTHON"],
            str(runner),
            "--weights",
            required["TRYON_WEIGHTS_PATH"],
            "--person",
            required["AYNA_TRYON_TATTOO_PERSON"],
            "--garment",
            required["AYNA_TRYON_TATTOO_GARMENT"],
            "--category",
            "tops",
            "--output",
            str(output),
            "--debug-dir",
            str(debug),
            "--job-id",
            "tattoo-regression",
            "--skin-recovery",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    run_debug = debug / "tattoo-regression"
    source = Image.open(required["AYNA_TRYON_TATTOO_PERSON"]).convert("RGB")
    result = Image.open(output).convert("RGB")
    preserve = Image.open(run_debug / "10d_preserve_mask.png").convert("L")
    visible_skin = Image.open(run_debug / "10f_visible_skin.png").convert("L")
    selected = [bool(value) for value in preserve.get_flattened_data()]
    differences = [
        sum(abs(left - right) for left, right in zip(original, final, strict=True)) / 3
        for original, final, keep in zip(
            source.get_flattened_data(),
            result.get_flattened_data(),
            selected,
            strict=True,
        )
        if keep
    ]
    assert result.size == source.size
    assert sum(differences) / max(1, len(differences)) < 0.1
    assert (
        local_contrast_energy(result, visible_skin)
        <= local_contrast_energy(source, visible_skin) + 1.0
    )
