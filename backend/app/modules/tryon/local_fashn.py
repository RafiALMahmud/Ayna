"""Isolated offline FASHN VTON v1.5 subprocess integration."""

import io
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from app.common.config import get_settings


class TryOnInferenceError(RuntimeError):
    pass


def infer(
    person: bytes,
    garment: bytes,
    category: str,
    *,
    cancelled: Callable[[], bool],
) -> tuple[bytes, dict]:
    settings = get_settings()
    python = Path(settings.tryon_python or "")
    source = Path(settings.tryon_source_path or "")
    weights = Path(settings.tryon_weights_path or "")
    runner = Path(__file__).resolve().parents[4] / "scripts" / "local_fashn_vton.py"
    if not python.is_file() or not source.is_dir() or not weights.is_dir() or not runner.is_file():
        raise TryOnInferenceError("TRYON_MODEL_NOT_CONFIGURED")
    with tempfile.TemporaryDirectory(prefix="ayna-fashn-") as temporary:
        root = Path(temporary)
        person_path, garment_path, output_path = (
            root / "person.png",
            root / "garment.png",
            root / "result.png",
        )
        Image.open(io.BytesIO(person)).convert("RGB").save(person_path, "PNG")
        Image.open(io.BytesIO(garment)).convert("RGB").save(garment_path, "PNG")
        command = [
            str(python),
            str(runner),
            "--weights",
            str(weights),
            "--person",
            str(person_path),
            "--garment",
            str(garment_path),
            "--category",
            category,
            "--output",
            str(output_path),
        ]
        process = subprocess.Popen(
            command,
            cwd=source,
            env={
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "HF_HOME": str(weights / "hf-cache"),
                "MPLCONFIGDIR": str(weights / "matplotlib-cache"),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + settings.tryon_timeout_seconds
        while process.poll() is None:
            if cancelled():
                process.kill()
                process.wait(timeout=10)
                raise TryOnInferenceError("TRYON_CANCELLED")
            if time.monotonic() >= deadline:
                process.kill()
                process.wait(timeout=10)
                raise TryOnInferenceError("TRYON_TIMEOUT")
            time.sleep(1)
        log = process.stdout.read()[-4000:] if process.stdout else ""
        if process.returncode or not output_path.is_file():
            raise TryOnInferenceError("TRYON_INFERENCE_FAILED")
        try:
            timing = json.loads(log.splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            timing = {}
        return output_path.read_bytes(), timing
