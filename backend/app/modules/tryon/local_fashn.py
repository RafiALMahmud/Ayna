"""Isolated offline FASHN VTON v1.5 subprocess integration."""

import io
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from app.common.config import get_settings


class TryOnInferenceError(RuntimeError):
    def __init__(self, code: str, diagnostics: dict | None = None):
        super().__init__(code)
        self.code = code
        self.diagnostics = diagnostics or {}


EVENT_PREFIX = "AYNA_STAGE "
STAGE_PROGRESS = {
    "process_startup": 10,
    "model_loading": 20,
    "pose_detection": 35,
    "human_parsing": 50,
    "garment_preprocessing": 65,
    "cuda_synthesis": 75,
    "output_parsing": 85,
    "skin_recovery": 90,
    "detail_restoration": 93,
    "image_encoding": 95,
    "output_validation": 95,
}
WINDOWS = os.name == "nt"


def terminate_process_tree(process, timeout: int = 15) -> dict:
    """Terminate the launcher and every descendant without masking the primary error."""
    if process.poll() is not None:
        return {"tree_terminated": True, "already_exited": True}
    diagnostics: dict = {"tree_terminated": False}
    try:
        if WINDOWS:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            diagnostics["taskkill_returncode"] = result.returncode
            if result.returncode != 0:
                raise RuntimeError("taskkill could not terminate the complete process tree")
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # type: ignore[attr-defined]
        process.wait(timeout=timeout)
        diagnostics["tree_terminated"] = True
    except Exception as exc:
        diagnostics["termination_warning"] = type(exc).__name__
        try:
            process.kill()
            process.wait(timeout=timeout)
        except Exception as fallback_exc:
            diagnostics["fallback_warning"] = type(fallback_exc).__name__
    return diagnostics


def _cleanup_directory(root: Path) -> str | None:
    for _ in range(5):
        try:
            shutil.rmtree(root)
            return None
        except FileNotFoundError:
            return None
        except PermissionError:
            time.sleep(0.25)
    return "PermissionError"


def _sanitized_log(text: str, *, root: Path, weights: Path, source: Path) -> str:
    value = text.replace("\x00", "")
    value = re.sub(r"\x1b\[[0-9;]*m", "", value)
    for private_path, replacement in (
        (root, "<temporary>"),
        (weights, "<weights>"),
        (source, "<source>"),
    ):
        value = value.replace(str(private_path), replacement)
    return value[-16_000:]


def _preserve_failure_log(
    text: str,
    *,
    root: Path,
    weights: Path,
    source: Path,
    job_id: str,
) -> bool:
    try:
        directory = Path(get_settings().tryon_log_path)
        directory.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^a-zA-Z0-9-]", "", job_id)[:64] or "unknown"
        (directory / f"{safe_id}.log").write_text(
            _sanitized_log(text, root=root, weights=weights, source=source),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def _read_failure_log(path: Path, current: str) -> str:
    try:
        return (current + path.read_text(encoding="utf-8", errors="replace"))[-32_000:]
    except OSError:
        return current


def _validate_result(path: Path) -> bytes:
    if not path.is_file():
        raise TryOnInferenceError("TRYON_OUTPUT_MISSING")
    try:
        data = path.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format != "PNG" or min(image.size) < 256:
                raise TryOnInferenceError("TRYON_OUTPUT_INVALID")
        return data
    except TryOnInferenceError:
        raise
    except Exception as exc:
        raise TryOnInferenceError("TRYON_OUTPUT_INVALID") from exc


def infer(
    person: bytes,
    garment: bytes,
    category: str,
    *,
    cancelled: Callable[[], bool],
    job_id: str = "unknown",
    stage_callback: Callable[[dict], None] | None = None,
) -> tuple[bytes, dict]:
    settings = get_settings()
    python = Path(settings.tryon_python or "")
    source = Path(settings.tryon_source_path or "")
    weights = Path(settings.tryon_weights_path or "")
    runner = Path(__file__).resolve().parents[4] / "scripts" / "local_fashn_vton.py"
    if not python.is_file() or not source.is_dir() or not weights.is_dir() or not runner.is_file():
        raise TryOnInferenceError("TRYON_MODEL_NOT_CONFIGURED")
    root = Path(tempfile.mkdtemp(prefix="ayna-fashn-"))
    caught: TryOnInferenceError | None = None
    process: subprocess.Popen[str] | None = None
    log_text = ""
    log_path = root / "inference.log"
    try:
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
        if getattr(settings, "tryon_debug", False):
            command.extend(
                [
                    "--job-id",
                    job_id,
                    "--debug-dir",
                    str(
                        Path(
                            getattr(settings, "tryon_debug_path", "../.data/tryon-debug")
                        ).resolve()
                    ),
                ]
            )
        command.append(
            "--skin-recovery"
            if getattr(settings, "tryon_skin_recovery", True)
            else "--no-skin-recovery"
        )
        command.append("--restore" if getattr(settings, "tryon_restore", False) else "--no-restore")
        # Do not leave verbose model/tqdm output in an unread PIPE: its bounded Windows
        # buffer can fill and deadlock the child before inference completes.
        with log_path.open("w+", encoding="utf-8", errors="replace") as log_file:
            child_env = {
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "HF_HOME": str(weights / "hf-cache"),
                "MPLCONFIGDIR": str(weights / "matplotlib-cache"),
                "OMP_NUM_THREADS": "4",
                "MKL_NUM_THREADS": "4",
                "TOKENIZERS_PARALLELISM": "false",
            }
            if WINDOWS:
                process = subprocess.Popen(
                    command,
                    cwd=source,
                    env=child_env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                process = subprocess.Popen(
                    command,
                    cwd=source,
                    env=child_env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
            if stage_callback:
                stage_callback(
                    {"stage": "process_startup", "event": "started", "elapsed_seconds": 0.0}
                )
            deadline = time.monotonic() + settings.tryon_timeout_seconds
            offset = 0

            def drain_events() -> None:
                nonlocal offset, log_text
                log_file.flush()
                log_file.seek(offset)
                chunk = log_file.read()
                offset = log_file.tell()
                if not chunk:
                    return
                log_text = (log_text + chunk)[-32_000:]
                if not stage_callback:
                    return
                for line in chunk.splitlines():
                    if not line.startswith(EVENT_PREFIX):
                        continue
                    try:
                        event = json.loads(line[len(EVENT_PREFIX) :])
                    except json.JSONDecodeError:
                        continue
                    if event.get("stage") in STAGE_PROGRESS:
                        stage_callback(event)

            while process.poll() is None:
                drain_events()
                if cancelled():
                    termination = terminate_process_tree(process)
                    drain_events()
                    raise TryOnInferenceError("TRYON_CANCELLED", termination)
                if time.monotonic() >= deadline:
                    termination = terminate_process_tree(process)
                    drain_events()
                    raise TryOnInferenceError("TRYON_TIMEOUT", termination)
                time.sleep(1)
            drain_events()
            log_file.seek(0)
            log = log_file.read()[-4000:]
        if process.returncode or not output_path.is_file():
            raise TryOnInferenceError(
                "TRYON_INFERENCE_FAILED", {"subprocess_returncode": process.returncode}
            )
        try:
            timing = json.loads(log.splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            timing = {}
        if stage_callback:
            stage_callback(
                {
                    "stage": "output_validation",
                    "event": "started",
                    "elapsed_seconds": timing.get("elapsed_seconds"),
                }
            )
        result = _validate_result(output_path)
        if stage_callback:
            stage_callback(
                {
                    "stage": "output_validation",
                    "event": "completed",
                    "elapsed_seconds": timing.get("elapsed_seconds"),
                }
            )
        return result, timing
    except TryOnInferenceError as exc:
        caught = exc
        if (
            not exc.diagnostics.get("tree_terminated")
            and process is not None
            and process.poll() is None
        ):
            for key, value in terminate_process_tree(process).items():
                exc.diagnostics.setdefault(key, value)
        log_text = _read_failure_log(log_path, log_text)
        exc.diagnostics["failure_log_retained"] = _preserve_failure_log(
            log_text,
            root=root,
            weights=weights,
            source=source,
            job_id=job_id,
        )
        raise
    except Exception as exc:
        caught = TryOnInferenceError(
            "TRYON_INFERENCE_FAILED", {"exception_type": type(exc).__name__}
        )
        if process is not None and process.poll() is None:
            caught.diagnostics.update(terminate_process_tree(process))
        log_text = _read_failure_log(log_path, log_text)
        caught.diagnostics["failure_log_retained"] = _preserve_failure_log(
            log_text,
            root=root,
            weights=weights,
            source=source,
            job_id=job_id,
        )
        raise caught from exc
    finally:
        cleanup_warning = _cleanup_directory(root)
        if caught and cleanup_warning:
            caught.diagnostics["cleanup_warning"] = cleanup_warning
