"""Offline TripoSR runner with a CPU scikit-image marching-cubes fallback.

The upstream project imports a compiled torchmcubes extension that has no
Windows wheel. This MIT-compatible boundary preserves upstream inference and
uses scikit-image only for iso-surface extraction.
"""

import argparse
import json
import sys
import time
import types
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from skimage.measure import marching_cubes as skimage_marching_cubes


def marching_cubes(level: torch.Tensor, threshold: float):
    vertices, faces, _normals, _values = skimage_marching_cubes(
        level.detach().cpu().numpy(), level=threshold
    )
    return torch.from_numpy(vertices.copy()).float(), torch.from_numpy(faces.copy()).long()


shim = types.ModuleType("torchmcubes")
shim.marching_cubes = marching_cubes
sys.modules["torchmcubes"] = shim


def prepare_image(path: str) -> tuple[Image.Image, dict]:
    """Apply bounded GrabCut isolation; fail rather than accept an empty mask."""
    source = cv2.imread(path, cv2.IMREAD_COLOR)
    if source is None:
        raise ValueError("Input image could not be decoded")
    height, width = source.shape[:2]
    margin = max(2, round(min(width, height) * 0.03))
    mask = np.zeros((height, width), np.uint8)
    background = np.zeros((1, 65), np.float64)
    foreground = np.zeros((1, 65), np.float64)
    cv2.grabCut(
        source,
        mask,
        (margin, margin, width - 2 * margin, height - 2 * margin),
        background,
        foreground,
        5,
        cv2.GC_INIT_WITH_RECT,
    )
    keep = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    components, labels, stats, _centroids = cv2.connectedComponentsWithStats(keep, 8)
    if components <= 1:
        raise ValueError("No isolated foreground was detected")
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = (labels == largest).astype(np.uint8)
    fraction = float(keep.mean())
    if not 0.05 <= fraction <= 0.9:
        raise ValueError("Foreground isolation was ambiguous")
    x, y, object_width, object_height = stats[largest, :4]
    padding = max(4, round(max(object_width, object_height) * 0.08))
    x0, y0 = max(0, x - padding), max(0, y - padding)
    x1, y1 = min(width, x + object_width + padding), min(height, y + object_height + padding)
    rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
    composed = np.full_like(rgb, 128)
    composed[keep.astype(bool)] = rgb[keep.astype(bool)]
    crop = composed[y0:y1, x0:x1]
    side = max(crop.shape[:2])
    square = np.full((side, side, 3), 128, dtype=np.uint8)
    top, left = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
    square[top : top + crop.shape[0], left : left + crop.shape[1]] = crop
    return Image.fromarray(square).resize((512, 512), Image.Resampling.LANCZOS), {
        "method": "opencv_grabcut_largest_component",
        "foreground_fraction": round(fraction, 5),
        "source_size": [width, height],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--chunk-size", type=int, default=4096)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.source).resolve()))

    from tsr.models.tokenizers import image as image_tokenizer
    from tsr.system import TSR

    dino_config = Path(args.model) / "dino-vitb16-config.json"
    if not dino_config.is_file():
        raise FileNotFoundError("Pinned DINO ViT-B/16 config is missing from the model directory")

    def local_encoder_config(*_args, **_kwargs) -> str:
        return str(dino_config)

    image_tokenizer.hf_hub_download = local_encoder_config

    started = time.perf_counter()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    model = TSR.from_pretrained(args.model, config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(args.chunk_size)
    model.to(device)
    image, preprocessing = prepare_image(args.image)
    with torch.inference_mode():
        scene_codes = model([image], device=device)
        meshes = model.extract_mesh(scene_codes, True, resolution=args.resolution)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    meshes[0].export(output)
    peak = (
        round(torch.cuda.max_memory_allocated() / 1024**2, 2) if device.startswith("cuda") else None
    )
    print(
        json.dumps(
            {
                "device": device,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "peak_cuda_mib": peak,
                "triangles": int(len(meshes[0].faces)),
                "vertices": int(len(meshes[0].vertices)),
                "preprocessing": preprocessing,
            }
        )
    )


if __name__ == "__main__":
    main()
