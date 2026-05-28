"""Run folder layout for PrintPipe artifacts."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from printpipe.contracts import ArtifactKind, InputKind


STAGE_DIRS: tuple[tuple[str, str], ...] = (
    ("input", "00_input"),
    ("frames", "10_frames"),
    ("meshgen", "20_meshgen"),
    ("repair", "30_repair"),
    ("geometry", "40_geometry"),
    ("profiles", "50_profiles"),
    ("bundle", "60_bundle"),
    ("slice", "70_slice"),
    ("reports", "80_reports"),
)


@dataclass(frozen=True)
class RunLayout:
    run_id: str
    root: Path
    input_dir: Path
    frames_dir: Path
    meshgen_dir: Path
    repair_dir: Path
    geometry_dir: Path
    profiles_dir: Path
    bundle_dir: Path
    slice_dir: Path
    reports_dir: Path
    manifest_path: Path
    original_input: Path


def infer_input_kind(path: Path) -> InputKind:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return InputKind.IMAGE
    if suffix == ".gif":
        return InputKind.GIF
    if suffix in {".mov", ".mp4", ".m4v", ".avi", ".webm"}:
        return InputKind.VIDEO
    if suffix in {".stl", ".glb", ".gltf", ".obj", ".3mf"}:
        return InputKind.MESH
    raise ValueError(f"unsupported input type: {path.suffix or path.name}")


def make_run_id(input_path: Path, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", input_path.stem).strip("-").lower()
    return f"{timestamp}-{stem or 'input'}"


def create_run(input_path: Path, runs_dir: Path = Path("runs"), run_id: str | None = None) -> RunLayout:
    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    input_kind = infer_input_kind(input_path)
    actual_run_id = run_id or make_run_id(input_path)
    root = runs_dir.expanduser().resolve() / actual_run_id
    root.mkdir(parents=True, exist_ok=False)

    dirs: dict[str, Path] = {}
    for key, dirname in STAGE_DIRS:
        dirs[key] = root / dirname
        dirs[key].mkdir()

    original_input = dirs["input"] / input_path.name
    shutil.copy2(input_path, original_input)

    manifest_path = root / "manifest.json"
    manifest = {
        "schema_version": 1,
        "run_id": actual_run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "kind": input_kind.value,
            "source_path": str(input_path),
            "artifact_kind": ArtifactKind.ORIGINAL_INPUT.value,
            "stored_path": str(original_input.relative_to(root)),
        },
        "stages": {key: dirname for key, dirname in STAGE_DIRS},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return RunLayout(
        run_id=actual_run_id,
        root=root,
        input_dir=dirs["input"],
        frames_dir=dirs["frames"],
        meshgen_dir=dirs["meshgen"],
        repair_dir=dirs["repair"],
        geometry_dir=dirs["geometry"],
        profiles_dir=dirs["profiles"],
        bundle_dir=dirs["bundle"],
        slice_dir=dirs["slice"],
        reports_dir=dirs["reports"],
        manifest_path=manifest_path,
        original_input=original_input,
    )


def load_run(run_root: str | Path) -> RunLayout:
    """Load a RunLayout from an existing run folder manifest."""

    root = Path(run_root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {manifest_path}")

    stages = payload.get("stages")
    if not isinstance(stages, dict):
        raise ValueError(f"run manifest is missing stage directories: {manifest_path}")

    dirs: dict[str, Path] = {}
    for key, dirname in STAGE_DIRS:
        directory = stages.get(key, dirname)
        if not isinstance(directory, str) or not directory:
            raise ValueError(f"run manifest has invalid stage directory for {key}")
        dirs[key] = root / directory

    input_info = payload.get("input")
    if not isinstance(input_info, dict):
        raise ValueError(f"run manifest is missing input metadata: {manifest_path}")
    stored_path = input_info.get("stored_path")
    if not isinstance(stored_path, str) or not stored_path:
        raise ValueError(f"run manifest is missing input stored_path: {manifest_path}")

    run_id = str(payload.get("run_id") or root.name)
    return RunLayout(
        run_id=run_id,
        root=root,
        input_dir=dirs["input"],
        frames_dir=dirs["frames"],
        meshgen_dir=dirs["meshgen"],
        repair_dir=dirs["repair"],
        geometry_dir=dirs["geometry"],
        profiles_dir=dirs["profiles"],
        bundle_dir=dirs["bundle"],
        slice_dir=dirs["slice"],
        reports_dir=dirs["reports"],
        manifest_path=manifest_path,
        original_input=root / stored_path,
    )
