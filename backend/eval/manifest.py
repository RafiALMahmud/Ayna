"""Consent-gated evaluation manifest loading and validation."""

import json
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TRANSITIONS = {
    "long-to-short",
    "bare-arm",
    "non-tee",
    "short-to-short",
    "short-to-long",
    "sleeveless",
}


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    person: Path
    garment: Path
    category: str
    transition: str
    consent: bool


@dataclass(frozen=True)
class EvalManifest:
    cases: tuple[EvalCase, ...]
    synthetic: bool = False


def load_manifest(path: Path, *, require_files: bool = True) -> EvalManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError("manifest must contain version 1 and a cases array")
    synthetic = bool(data.get("synthetic", False))
    rows = data["cases"]
    if not synthetic and not 50 <= len(rows) <= 100:
        raise ValueError("a real evaluation manifest must contain 50 to 100 cases")
    if synthetic and not rows:
        raise ValueError("a synthetic manifest must not be empty")
    cases = []
    seen = set()
    for row in rows:
        case_id = str(row.get("id", "")).strip()
        if not case_id or case_id in seen:
            raise ValueError("case ids must be non-empty and unique")
        seen.add(case_id)
        if row.get("consent") is not True:
            raise PermissionError(f"case {case_id} has no affirmative consent")
        transition = str(row.get("transition", ""))
        if transition not in ALLOWED_TRANSITIONS:
            raise ValueError(f"case {case_id} has unsupported transition {transition!r}")
        person = Path(row["person"])
        garment = Path(row["garment"])
        if require_files and (not person.is_file() or not garment.is_file()):
            raise FileNotFoundError(f"private fixture missing for case {case_id}")
        cases.append(
            EvalCase(case_id, person, garment, str(row.get("category", "tops")), transition, True)
        )
    return EvalManifest(tuple(cases), synthetic)
