"""Small offline CLI boundary for the optional FASHN VTON environment."""

import argparse
import json
import time
from pathlib import Path

import torch
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--person", required=True)
    parser.add_argument("--garment", required=True)
    parser.add_argument("--category", choices=["tops", "bottoms", "one-pieces"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    from fashn_human_parser import FashnHumanParser as UpstreamHumanParser
    from fashn_vton import pipeline as pipeline_module
    from fashn_vton import TryOnPipeline

    parser_path = Path(args.weights) / "parser"
    if not parser_path.is_dir():
        raise FileNotFoundError("Pinned local human parser weights are missing")

    class LocalHumanParser(UpstreamHumanParser):
        def __init__(self, device=None):
            super().__init__(model_id=str(parser_path), device=device)

    pipeline_module.FashnHumanParser = LocalHumanParser

    started = time.perf_counter()
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    pipeline = TryOnPipeline(weights_dir=args.weights)
    result = pipeline(
        person_image=Image.open(args.person).convert("RGB"),
        garment_image=Image.open(args.garment).convert("RGB"),
        category=args.category,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.images[0].save(output, "PNG", optimize=True)
    print(
        json.dumps(
            {
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "device": "cuda:0" if torch.cuda.is_available() else "cpu",
                "peak_cuda_mib": (
                    round(torch.cuda.max_memory_allocated() / 1024**2, 2)
                    if torch.cuda.is_available()
                    else None
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
