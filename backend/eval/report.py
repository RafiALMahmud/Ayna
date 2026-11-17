"""Offline report and image artifact generation."""

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def side_by_side(left: Image.Image, right: Image.Image, output: Path) -> None:
    height = max(left.height, right.height)
    canvas = Image.new("RGB", (left.width + right.width, height), "white")
    canvas.paste(left.convert("RGB"), (0, 0))
    canvas.paste(right.convert("RGB"), (left.width, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")


def contact_sheet(images: list[tuple[str, Image.Image]], output: Path) -> None:
    thumbs = []
    for label, image in images[:10]:
        thumb = image.convert("RGB").copy()
        thumb.thumbnail((300, 300))
        tile = Image.new("RGB", (320, 340), "white")
        tile.paste(thumb, ((320 - thumb.width) // 2, 25))
        ImageDraw.Draw(tile).text((8, 8), label, fill="black")
        thumbs.append(tile)
    canvas = Image.new("RGB", (640, max(340, ((len(thumbs) + 1) // 2) * 340)), "white")
    for index, tile in enumerate(thumbs):
        canvas.paste(tile, ((index % 2) * 320, (index // 2) * 340))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")


def write_results(root: Path, rows: list[dict[str, Any]], capabilities: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"capabilities": capabilities, "cases": rows}
    (root / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Try-on evaluation",
        "",
        "| Case | L1 outside edit | SSIM | New marks |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['masked_l1']:.4f} | {row['ssim']:.4f} | {row['new_marks']:.4f} |"
        )
    lines += [
        "",
        "KID is preferred to FID for small samples because its polynomial-MMD estimator is "
        "unbiased; it is unavailable until an approved feature extractor is installed.",
    ]
    (root / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
