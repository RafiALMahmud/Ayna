"""Isolated optional Blender GLB optimization with strict validation and original fallback."""

from __future__ import annotations

import json
import struct
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from app.common.config import get_settings
from app.modules.generation.meshy import MAX_GLB_BYTES, validate_glb
from app.modules.quality.rendering import load_render_mesh, render_glb_views

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class OptimizationResult:
    glb: bytes
    original_glb: bytes
    metadata: dict


def _document(data: bytes) -> dict:
    size, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise ValueError("GLB JSON chunk is missing")
    return json.loads(data[20 : 20 + size].rstrip(b" \t\r\n\0"))


def _manifest(data: bytes) -> dict[str, int]:
    document = _document(data)
    primitives = [
        primitive for mesh in document.get("meshes", []) for primitive in mesh.get("primitives", [])
    ]
    return {
        "materials": len(document.get("materials", [])),
        "textures": len(document.get("textures", [])),
        "images": len(document.get("images", [])),
        "uv_primitives": sum("TEXCOORD_0" in item.get("attributes", {}) for item in primitives),
    }


def _render_difference(original: bytes, candidate: bytes) -> float:
    original_views = render_glb_views(original, 128).images
    candidate_views = render_glb_views(candidate, 128).images
    differences = []
    for view in sorted(set(original_views) & set(candidate_views)):
        with Image.open(BytesIO(original_views[view])) as left:
            with Image.open(BytesIO(candidate_views[view])) as right:
                difference = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
                differences.append(sum(ImageStat.Stat(difference).mean) / (3 * 255))
    if not differences:
        raise ValueError("No comparable Blender validation views")
    return round(sum(differences) / len(differences), 5)


def _validate_candidate(original: bytes, candidate: bytes, target_triangles: int) -> dict:
    validate_glb(candidate)
    if len(candidate) >= len(original):
        raise ValueError("optimized GLB is not smaller")
    source_mesh = load_render_mesh(original, max_triangles=100_000)
    candidate_mesh = load_render_mesh(candidate, max_triangles=100_000)
    if (
        len(source_mesh.triangles) > target_triangles
        and len(candidate_mesh.triangles) > target_triangles
    ):
        raise ValueError("optimized GLB exceeds the triangle target")
    radius_ratio = candidate_mesh.radius / source_mesh.radius
    if not 0.98 <= radius_ratio <= 1.02:
        raise ValueError("optimized bounds changed beyond tolerance")
    source_manifest, candidate_manifest = _manifest(original), _manifest(candidate)
    for field in ("materials", "textures", "images", "uv_primitives"):
        if candidate_manifest[field] < source_manifest[field]:
            raise ValueError(f"optimized GLB lost {field}")
    appearance_difference = _render_difference(original, candidate)
    if appearance_difference > 0.08:
        raise ValueError("optimized appearance changed beyond tolerance")
    return {
        "original_bytes": len(original),
        "optimized_bytes": len(candidate),
        "original_triangles": len(source_mesh.triangles),
        "optimized_triangles": len(candidate_mesh.triangles),
        "bounds_radius_ratio": round(radius_ratio, 5),
        "appearance_difference": appearance_difference,
        "manifest_before": source_manifest,
        "manifest_after": candidate_manifest,
    }


def optimize_with_blender(
    glb: bytes,
    *,
    runner: Runner = subprocess.run,
    command_prefix: Sequence[str] | None = None,
) -> OptimizationResult:
    """Return validated optimized bytes or the untouched original with a failure reason."""
    settings = get_settings()
    if not settings.blender_optimization_enabled:
        return OptimizationResult(glb, glb, {"status": "disabled"})
    executable = settings.blender_executable
    if not executable or not Path(executable).is_file():
        return OptimizationResult(glb, glb, {"status": "unavailable", "reason": "missing_blender"})
    validate_glb(glb)
    script = Path(__file__).resolve().parents[4] / "scripts" / "blender_optimize.py"
    try:
        with tempfile.TemporaryDirectory(prefix="ayna-blender-") as directory:
            root = Path(directory)
            source, output = root / "source.glb", root / "optimized.glb"
            source.write_bytes(glb)
            command = list(command_prefix or [executable, "--background", "--factory-startup"])
            command.extend(
                [
                    "--python",
                    str(script),
                    "--",
                    str(source),
                    str(output),
                    str(settings.blender_target_triangles),
                ]
            )
            completed = runner(
                command,
                check=False,
                capture_output=True,
                timeout=settings.blender_timeout_seconds,
            )
            if completed.returncode != 0 or not output.is_file():
                raise RuntimeError("Blender optimization subprocess failed")
            if output.stat().st_size > MAX_GLB_BYTES:
                raise ValueError("optimized GLB exceeds the byte limit")
            optimized = output.read_bytes()
            validation = _validate_candidate(glb, optimized, settings.blender_target_triangles)
            return OptimizationResult(
                optimized,
                glb,
                {"status": "optimized", "validator": "ayna-blender-validation-v1", **validation},
            )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return OptimizationResult(
            glb,
            glb,
            {"status": "fallback_original", "reason": exc.__class__.__name__},
        )
