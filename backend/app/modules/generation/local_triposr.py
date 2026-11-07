"""Isolated, offline TripoSR execution.

TripoSR consumes exactly one image. Ayna keeps the 2-5 photo capture/review
workflow, but only the seller's front (or first) view conditions this model.
"""

import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from app.common.config import get_settings
from app.common.storage import get_storage
from app.modules.generation.meshy import ProviderError
from app.modules.generation.providers import GenerationResult


class LocalTripoSRProvider:
    def __init__(
        self,
        *,
        progress: Callable[[int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ):
        self.progress = progress or (lambda _value: None)
        self.cancelled = cancelled or (lambda: False)

    def generate(self, image_keys: list[str]) -> GenerationResult:
        settings = get_settings()
        if not image_keys:
            raise ProviderError("LOCAL_INPUT_MISSING")
        python = Path(settings.local_triposr_python or "")
        source = Path(settings.local_triposr_source or "")
        model = Path(settings.local_triposr_model_path or "")
        runner = Path(__file__).resolve().parents[4] / "scripts" / "local_triposr_runner.py"
        if (
            not python.is_file()
            or not (source / "tsr" / "system.py").is_file()
            or not model.is_dir()
            or not runner.is_file()
        ):
            raise ProviderError("LOCAL_MODEL_NOT_CONFIGURED")

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="ayna-triposr-") as temporary:
            root = Path(temporary)
            input_path = root / "front.png"
            output_path = root / "mesh.glb"
            input_path.write_bytes(get_storage().get(image_keys[0]))
            command = [
                str(python),
                str(runner),
                "--source",
                str(source),
                "--model",
                str(model),
                "--image",
                str(input_path),
                "--output",
                str(output_path),
                "--resolution",
                str(settings.local_triposr_mc_resolution),
                "--chunk-size",
                "4096",
            ]
            environment = {
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "HF_HOME": str(model.parent / "hf-cache"),
            }
            self.progress(25)
            process = subprocess.Popen(
                command,
                cwd=source,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            deadline = time.monotonic() + settings.local_triposr_timeout_seconds
            while process.poll() is None:
                if self.cancelled():
                    process.kill()
                    process.wait(timeout=10)
                    raise ProviderError("CANCELLED")
                if time.monotonic() >= deadline:
                    process.kill()
                    process.wait(timeout=10)
                    raise ProviderError("LOCAL_MODEL_TIMEOUT")
                time.sleep(1)
            output = process.stdout.read()[-4000:] if process.stdout else ""
            if process.returncode:
                # Logs can contain local paths but never image bytes or credentials.
                raise ProviderError("LOCAL_MODEL_FAILED")
            if not output_path.is_file():
                raise ProviderError("LOCAL_OUTPUT_MISSING")
            glb = output_path.read_bytes()
            try:
                runtime = json.loads(output.splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                runtime = {}
            self.progress(75)
            return GenerationResult(
                glb,
                {
                    "provider": "local_triposr",
                    "model": "stabilityai/TripoSR",
                    "model_revision": "5b521936b01fbe1890f6f9baed0254ab6351c04a",
                    "encoder_config_revision": "f205d5d8e640a89a2b8ef0369670dfc37cc07fc2",
                    "code_revision": "107cefdc244c39106fa830359024f6a2f1c78871",
                    "license": "MIT",
                    "source_image_count": len(image_keys),
                    "conditioned_image_count": 1,
                    "ignored_image_count": max(0, len(image_keys) - 1),
                    "conditioning_view": "front_or_first",
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "runtime": runtime,
                    "sha256": hashlib.sha256(glb).hexdigest(),
                },
            )
