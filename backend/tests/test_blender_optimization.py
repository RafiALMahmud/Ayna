import struct
import subprocess
from types import SimpleNamespace

from app.common.config import get_settings
from app.modules.generation.blender import optimize_with_blender
from app.modules.generation.meshy import validate_glb
from app.modules.generation.providers import dummy_glb


def padded_dummy_glb() -> bytes:
    source = dummy_glb()
    json_size, json_kind = struct.unpack_from("<II", source, 12)
    document = source[20 : 20 + json_size].rstrip(b" ")
    padded = document + b" " * (512 - len(document) % 4)
    remaining = source[20 + json_size :]
    result = (
        struct.pack("<III", 0x46546C67, 2, 20 + len(padded) + len(remaining))
        + struct.pack("<II", len(padded), json_kind)
        + padded
        + remaining
    )
    validate_glb(result)
    return result


def test_blender_unavailable_preserves_original(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "blender_optimization_enabled", True)
    monkeypatch.setattr(settings, "blender_executable", "Z:/missing/blender.exe")
    source = dummy_glb()
    result = optimize_with_blender(source)
    assert result.glb == result.original_glb == source
    assert result.metadata == {"status": "unavailable", "reason": "missing_blender"}


def test_blender_candidate_must_preserve_bounds_materials_and_appearance(monkeypatch, tmp_path):
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"test fixture, not an executable")
    settings = get_settings()
    monkeypatch.setattr(settings, "blender_optimization_enabled", True)
    monkeypatch.setattr(settings, "blender_executable", str(executable))

    def runner(command, **_options):
        output = command[-2]
        with open(output, "wb") as file:
            file.write(dummy_glb())
        return SimpleNamespace(returncode=0)

    source = padded_dummy_glb()
    result = optimize_with_blender(source, runner=runner)
    assert result.glb == dummy_glb()
    assert result.original_glb == source
    assert result.metadata["status"] == "optimized"
    assert result.metadata["optimized_bytes"] < result.metadata["original_bytes"]
    assert result.metadata["bounds_radius_ratio"] == 1.0
    assert result.metadata["appearance_difference"] == 0.0


def test_blender_timeout_falls_back_to_original(monkeypatch, tmp_path):
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"test fixture")
    settings = get_settings()
    monkeypatch.setattr(settings, "blender_optimization_enabled", True)
    monkeypatch.setattr(settings, "blender_executable", str(executable))

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("blender", 1)

    source = dummy_glb()
    result = optimize_with_blender(source, runner=timeout)
    assert result.glb == source
    assert result.metadata == {"status": "fallback_original", "reason": "TimeoutExpired"}
