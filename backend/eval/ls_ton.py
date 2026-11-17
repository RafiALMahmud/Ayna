"""Disabled-by-default LS-TON manifest adapter; never downloads data."""

from pathlib import Path

from .manifest import EvalManifest, load_manifest


def load_ls_ton(root: Path, *, enabled: bool = False) -> EvalManifest:
    if not enabled:
        raise RuntimeError("LS-TON evaluation is disabled; verify dataset availability and license")
    return load_manifest(root / "manifest.json")
