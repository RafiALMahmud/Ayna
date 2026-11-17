"""Run a private baseline/fixed FASHN comparison and report quality metrics."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_variant(
    *,
    runner: Path,
    weights: Path,
    person: Path,
    garment: Path,
    category: str,
    output: Path,
    debug_dir: Path,
    recovery: bool,
) -> dict:
    command = [
        sys.executable,
        str(runner),
        "--weights",
        str(weights),
        "--person",
        str(person),
        "--garment",
        str(garment),
        "--category",
        category,
        "--output",
        str(output),
        "--job-id",
        "fixed" if recovery else "baseline",
        "--debug-dir",
        str(debug_dir),
        "--skin-recovery" if recovery else "--no-skin-recovery",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    return json.loads(completed.stdout.splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--person", required=True, type=Path)
    parser.add_argument("--garment", required=True, type=Path)
    parser.add_argument("--category", choices=["tops", "bottoms", "one-pieces"], required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(".data/eval"))
    args = parser.parse_args()

    import numpy as np
    from PIL import Image

    backend_path = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend_path))
    from app.modules.tryon.skin_recovery import skin_tone_delta

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = Path(__file__).with_name("local_fashn_vton.py")
    debug_dir = output_dir / "debug"
    baseline_path = output_dir / "baseline.png"
    fixed_path = output_dir / "fixed.png"

    baseline_runtime = run_variant(
        runner=runner,
        weights=args.weights,
        person=args.person,
        garment=args.garment,
        category=args.category,
        output=baseline_path,
        debug_dir=debug_dir,
        recovery=False,
    )
    fixed_runtime = run_variant(
        runner=runner,
        weights=args.weights,
        person=args.person,
        garment=args.garment,
        category=args.category,
        output=fixed_path,
        debug_dir=debug_dir,
        recovery=True,
    )

    fixed_debug = debug_dir / "fixed"
    core = Image.open(fixed_debug / "12b_skin_recovery_core.png").convert("L")
    support = Image.open(fixed_debug / "12c_skin_recovery_support.png").convert("L")
    sample = Image.open(fixed_debug / "12d_skin_sample_mask.png").convert("L")
    reference = Image.open(fixed_debug / "01_input_person.png").convert("RGB")
    baseline = Image.open(baseline_path).convert("RGB")
    fixed = Image.open(fixed_path).convert("RGB")

    baseline_delta = skin_tone_delta(baseline, core, reference, sample)
    fixed_delta = skin_tone_delta(fixed, core, reference, sample)
    fixed_array = np.asarray(fixed, dtype=np.int16)
    baseline_array = np.asarray(baseline, dtype=np.int16)
    support_array = np.asarray(support.resize(fixed.size, Image.Resampling.NEAREST), dtype=np.uint8)
    outside = support_array == 0
    outside_l1 = float(np.abs(fixed_array[outside] - baseline_array[outside]).mean())

    side_by_side = Image.new("RGB", (baseline.width * 2, baseline.height), "white")
    side_by_side.paste(baseline, (0, 0))
    side_by_side.paste(fixed, (baseline.width, 0))
    side_by_side.save(output_dir / "baseline_vs_fixed.png", "PNG", optimize=True)

    summary = {
        "baseline_elapsed_seconds": baseline_runtime.get("elapsed_seconds"),
        "fixed_elapsed_seconds": fixed_runtime.get("elapsed_seconds"),
        "fixed_peak_cuda_mib": fixed_runtime.get("peak_cuda_mib"),
        "baseline_skin_tone_delta_lab": baseline_delta,
        "fixed_skin_tone_delta_lab": fixed_delta,
        "outside_edit_mask_l1": outside_l1,
        "skin_recovery_applied": fixed_runtime.get("skin_recovery_applied"),
        "sleeve_case": fixed_runtime.get("sleeve_case"),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
