"""Evaluate already-generated named configurations without moving private images."""

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageChops

from .manifest import load_manifest
from .metrics import masked_l1, masked_ssim, metric_capabilities, new_marks_score
from .report import contact_sheet, side_by_side, write_results


def generate_outputs(
    manifest_path: Path,
    run_name: str,
    data_root: Path,
    *,
    python: Path,
    runner: Path,
    weights: Path,
) -> None:
    """Run the local pipeline sequentially for a consent-validated manifest."""
    manifest = load_manifest(manifest_path)
    output_root = data_root / run_name / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    for case in manifest.cases:
        completed = subprocess.run(
            [
                str(python),
                str(runner),
                "--weights",
                str(weights),
                "--person",
                str(case.person),
                "--garment",
                str(case.garment),
                "--category",
                case.category,
                "--output",
                str(output_root / f"{case.case_id}.png"),
                "--job-id",
                f"eval-{case.case_id}",
                "--skin-recovery",
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"local pipeline failed for consented case {case.case_id}")


def evaluate(manifest_path: Path, run_name: str, data_root: Path) -> Path:
    manifest = load_manifest(manifest_path)
    root = data_root / run_name
    rows = []
    worst = []
    marks_by_case: dict[str, float] = {}
    for case in manifest.cases:
        output_path = root / "outputs" / f"{case.case_id}.png"
        if not output_path.is_file():
            raise FileNotFoundError(f"missing generated output for {case.case_id}")
        source = Image.open(case.person).convert("RGB")
        output = Image.open(output_path).convert("RGB").resize(source.size)
        changed = (
            ImageChops.difference(source, output)
            .convert("L")
            .point(lambda value: 255 if value > 24 else 0)
        )
        preserved = ImageChops.invert(changed)
        marks_score = new_marks_score(source, output, changed)
        row = {
            "id": case.case_id,
            "masked_l1": masked_l1(source, output, preserved),
            "ssim": masked_ssim(source, output, preserved),
            "new_marks": marks_score,
        }
        rows.append(row)
        marks_by_case[case.case_id] = marks_score
        comparison = root / "cases" / f"{case.case_id}.png"
        side_by_side(source, output, comparison)
        worst.append((case.case_id, Image.open(comparison).copy()))
    worst.sort(key=lambda item: marks_by_case[item[0]], reverse=True)
    contact_sheet(worst, root / "worst10.png")
    write_results(root, rows, metric_capabilities())
    return root


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--data-root", type=Path, default=Path(".data/eval"))
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--python", type=Path)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--weights", type=Path)
    args = parser.parse_args(argv)
    if args.generate:
        if not all((args.python, args.runner, args.weights)):
            parser.error("--generate requires --python, --runner and --weights")
        generate_outputs(
            args.manifest,
            args.run_name,
            args.data_root,
            python=args.python,
            runner=args.runner,
            weights=args.weights,
        )
    evaluate(args.manifest, args.run_name, args.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
