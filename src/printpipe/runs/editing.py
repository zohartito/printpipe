"""Edit recipe contracts for non-destructive run refinement."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from printpipe.runs.paths import STAGE_DIRS, RunLayout


EDIT_RECIPE_FILENAME = "edit_recipe.json"
EDIT_RECIPE_SCHEMA_VERSION = 1
SUPPORT_STRATEGIES = frozenset(
    {
        "auto",
        "snug_tree_auto",
        "tree",
        "minimal",
        "none",
    }
)


@dataclass(frozen=True)
class EditScale:
    overall: float = 1.0
    x: float = 1.0
    y: float = 1.0
    z: float = 1.0


@dataclass(frozen=True)
class EditTargets:
    length: float | None = None
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True)
class GeometryIntent:
    upper_width_delta_mm: float = 0.0
    opening_width_delta_mm: float = 0.0
    arch_height_delta_mm: float = 0.0
    wall_thickness_mm: float | None = None
    flat_base: bool = True


@dataclass(frozen=True)
class EditRecipe:
    parent_run_id: str
    scale: EditScale = field(default_factory=EditScale)
    targets_mm: EditTargets = field(default_factory=EditTargets)
    geometry_intent: GeometryIntent = field(default_factory=GeometryIntent)
    support_strategy: str = "auto"
    instruction: str = ""
    schema_version: int = EDIT_RECIPE_SCHEMA_VERSION


def edit_recipe_to_dict(recipe: EditRecipe) -> dict[str, Any]:
    """Convert an edit recipe to the canonical JSON payload."""

    validate_edit_recipe(recipe)
    return {
        "schema_version": recipe.schema_version,
        "parent_run_id": recipe.parent_run_id,
        "scale": {
            "overall": recipe.scale.overall,
            "x": recipe.scale.x,
            "y": recipe.scale.y,
            "z": recipe.scale.z,
        },
        "targets_mm": {
            "length": recipe.targets_mm.length,
            "width": recipe.targets_mm.width,
            "height": recipe.targets_mm.height,
        },
        "geometry_intent": {
            "upper_width_delta_mm": recipe.geometry_intent.upper_width_delta_mm,
            "opening_width_delta_mm": recipe.geometry_intent.opening_width_delta_mm,
            "arch_height_delta_mm": recipe.geometry_intent.arch_height_delta_mm,
            "wall_thickness_mm": recipe.geometry_intent.wall_thickness_mm,
            "flat_base": recipe.geometry_intent.flat_base,
        },
        "support_strategy": recipe.support_strategy,
        "instruction": recipe.instruction,
    }


def edit_recipe_from_dict(payload: dict[str, Any]) -> EditRecipe:
    """Parse the canonical JSON payload into an edit recipe."""

    if payload.get("schema_version") != EDIT_RECIPE_SCHEMA_VERSION:
        raise ValueError("unsupported edit recipe schema_version")

    scale = _mapping(payload.get("scale"))
    targets = _mapping(payload.get("targets_mm"))
    intent = _mapping(payload.get("geometry_intent"))

    recipe = EditRecipe(
        schema_version=EDIT_RECIPE_SCHEMA_VERSION,
        parent_run_id=_required_string(payload.get("parent_run_id"), "parent_run_id"),
        scale=EditScale(
            overall=_positive_number(scale.get("overall"), default=1.0),
            x=_positive_number(scale.get("x"), default=1.0),
            y=_positive_number(scale.get("y"), default=1.0),
            z=_positive_number(scale.get("z"), default=1.0),
        ),
        targets_mm=EditTargets(
            length=_optional_positive_number(targets.get("length")),
            width=_optional_positive_number(targets.get("width")),
            height=_optional_positive_number(targets.get("height")),
        ),
        geometry_intent=GeometryIntent(
            upper_width_delta_mm=_number(
                intent.get("upper_width_delta_mm"),
                default=0.0,
            ),
            opening_width_delta_mm=_number(
                intent.get("opening_width_delta_mm"),
                default=0.0,
            ),
            arch_height_delta_mm=_number(intent.get("arch_height_delta_mm"), default=0.0),
            wall_thickness_mm=_optional_positive_number(intent.get("wall_thickness_mm")),
            flat_base=_bool(intent.get("flat_base", True)),
        ),
        support_strategy=str(payload.get("support_strategy", "auto")),
        instruction=str(payload.get("instruction", "")),
    )
    validate_edit_recipe(recipe)
    return recipe


def validate_edit_recipe(recipe: EditRecipe) -> None:
    """Raise ValueError if an edit recipe is unsafe or ambiguous."""

    if not recipe.parent_run_id.strip():
        raise ValueError("edit recipe parent_run_id is required")
    for field_name, value in (
        ("overall_scale", recipe.scale.overall),
        ("x_scale", recipe.scale.x),
        ("y_scale", recipe.scale.y),
        ("z_scale", recipe.scale.z),
    ):
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
    for field_name, value in (
        ("target_length_mm", recipe.targets_mm.length),
        ("target_width_mm", recipe.targets_mm.width),
        ("target_height_mm", recipe.targets_mm.height),
        ("wall_thickness_mm", recipe.geometry_intent.wall_thickness_mm),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{field_name} must be positive")
    if recipe.support_strategy not in SUPPORT_STRATEGIES:
        raise ValueError(f"unsupported support_strategy: {recipe.support_strategy}")


def write_edit_recipe(run_root: str | Path, recipe: EditRecipe) -> Path:
    """Write edit_recipe.json into a run folder."""

    root = Path(run_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / EDIT_RECIPE_FILENAME
    path.write_text(
        json.dumps(edit_recipe_to_dict(recipe), indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_edit_recipe(run_root: str | Path) -> EditRecipe:
    """Load edit_recipe.json from a run folder."""

    path = Path(run_root).expanduser().resolve() / EDIT_RECIPE_FILENAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("edit recipe must be a JSON object")
    return edit_recipe_from_dict(payload)


def next_edit_run_id(parent_run_root: str | Path) -> str:
    """Return the next sibling run id for an edit of the given parent run."""

    parent_root = Path(parent_run_root).expanduser().resolve()
    prefix = f"{parent_root.name}_edit_"
    highest = 0
    if parent_root.parent.exists():
        for sibling in parent_root.parent.iterdir():
            match = re.fullmatch(rf"{re.escape(prefix)}(\d{{3}})", sibling.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:03d}"


def create_edit_run(
    parent_run_root: str | Path,
    recipe: EditRecipe,
    *,
    run_id: str | None = None,
    runs_dir: str | Path | None = None,
) -> RunLayout:
    """Create a new run folder that points back to a parent run plus edit recipe."""

    parent_root = Path(parent_run_root).expanduser().resolve()
    parent_manifest = _read_json(parent_root / "manifest.json")
    edit_run_id = run_id or next_edit_run_id(parent_root)
    root = (
        Path(runs_dir).expanduser().resolve()
        if runs_dir
        else parent_root.parent
    ) / edit_run_id
    root.mkdir(parents=True, exist_ok=False)

    dirs: dict[str, Path] = {}
    for key, dirname in STAGE_DIRS:
        dirs[key] = root / dirname
        dirs[key].mkdir()

    parent_input = _mapping(parent_manifest.get("input"))
    original_input = _copy_parent_input(parent_root, parent_input, dirs["input"])
    manifest_path = root / "manifest.json"
    manifest = {
        "schema_version": 1,
        "run_id": edit_run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_run": {
            "run_id": str(parent_manifest.get("run_id", parent_root.name)),
            "run_root": str(parent_root),
        },
        "input": {
            **parent_input,
            "stored_path": _relative_to_run(original_input, root),
        },
        "edit_recipe": {
            "path": EDIT_RECIPE_FILENAME,
        },
        "stages": {key: dirname for key, dirname in STAGE_DIRS},
    }
    if "launch_options" in parent_manifest:
        manifest["launch_options"] = parent_manifest["launch_options"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_edit_recipe(root, recipe)

    return RunLayout(
        run_id=edit_run_id,
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


def _copy_parent_input(
    parent_root: Path,
    parent_input: dict[str, Any],
    input_dir: Path,
) -> Path:
    stored_path = parent_input.get("stored_path")
    if isinstance(stored_path, str) and stored_path:
        source = parent_root / stored_path
        if source.exists():
            destination = input_dir / source.name
            shutil.copy2(source, destination)
            return destination

    destination = input_dir / "inherited_input.placeholder"
    destination.write_text(
        "Parent input could not be copied; see parent_run in manifest.\n",
        encoding="utf-8",
    )
    return destination


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _required_string(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _number(value: Any, *, default: float) -> float:
    import math

    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid numbers")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("number must be finite")
    return parsed


def _positive_number(value: Any, *, default: float) -> float:
    parsed = _number(value, default=default)
    if parsed <= 0:
        raise ValueError("number must be positive")
    return parsed


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    return _number(value, default=0.0)


def _optional_positive_number(value: Any) -> float | None:
    parsed = _optional_number(value)
    if parsed is not None and parsed <= 0:
        raise ValueError("number must be positive")
    return parsed


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ValueError("expected boolean value")


def _relative_to_run(path: Path, run_root: Path) -> str:
    try:
        return path.resolve().relative_to(run_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


__all__ = [
    "EDIT_RECIPE_FILENAME",
    "SUPPORT_STRATEGIES",
    "EditRecipe",
    "EditScale",
    "EditTargets",
    "GeometryIntent",
    "create_edit_run",
    "edit_recipe_from_dict",
    "edit_recipe_to_dict",
    "load_edit_recipe",
    "next_edit_run_id",
    "validate_edit_recipe",
    "write_edit_recipe",
]
