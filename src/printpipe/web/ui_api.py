"""Server-side UI-API for the friend-usable PrintPipe web UI.

Pure Python helpers with NO HTTP routing -- the integrator wires routes onto
``PrintPipeWebApp``. Each function takes plain paths/dicts and returns plain
dicts (or a ``Path``) so they can back any of:

* ``GET  /runs/<id>/model.glb``   -> :func:`export_run_glb`
* ``GET  /api/settings?material=`` -> :func:`list_settings`
* ``POST /runs/<id>/reslice``      -> :func:`reslice`
* ``GET  /runs/<id>/status.json``  -> :func:`slice_status`

The slicer-result and gcode-header formats mirror what
``printpipe.bambu.slicer`` already writes (``slice_result.json`` keys:
``time_seconds``, ``filament_g``, ``layer_count``, ``gcode_path``).
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from printpipe.pipeline import (
    resolve_slice_settings,
    run_existing_mesh_pipeline_on_layout,
)
from printpipe.runs import RunLayout, load_run
from printpipe.web.artifacts import discover_run_artifacts


# Mesh categories the 3D viewer can display, best-first. Mirrors
# run_detail.py's _PRIMARY_ARTIFACT_TILES ordering.
_MESH_CATEGORIES: tuple[str, ...] = (
    "oriented_mesh",
    "repaired_mesh",
    "generated_mesh",
    "calibration_mesh",
)

# UI-friendly subset surfaced in the settings panel. Order is the panel order.
_PANEL_KEYS: tuple[str, ...] = (
    "layer_height",
    "wall_loops",
    "sparse_infill_density",
    "enable_support",
    "support_type",
    "support_style",
    "outer_wall_speed",
)


def export_run_glb(run_root: str | Path) -> Path:
    """Find a run's primary STL/mesh, export a ``.glb`` next to it, return it.

    Caches: if a ``.glb`` already exists and is newer than the source mesh, the
    existing file is returned without re-exporting. PrintPipe writes ASCII STL;
    ``trimesh.load`` handles that transparently.
    """

    layout = _load_layout(run_root)
    source_mesh = _primary_mesh_path(layout)
    if source_mesh is None:
        raise FileNotFoundError(f"no mesh artifact found for run {layout.run_id}")

    glb_path = source_mesh.with_suffix(".glb")
    if glb_path.exists() and glb_path.stat().st_mtime >= source_mesh.stat().st_mtime:
        return glb_path

    import trimesh  # imported lazily so the module loads without the slicer present

    mesh = trimesh.load(source_mesh, force="mesh")
    mesh.export(glb_path, file_type="glb")
    return glb_path


def list_settings(material: str) -> dict[str, Any]:
    """Return a small, UI-friendly slice-settings view for the panel.

    Wraps :func:`resolve_slice_settings`. List-valued Bambu config entries are
    coerced to scalars for display. The ``counts`` block carries the full
    keyspace sizes so the UI can show "194 process settings" etc.
    """

    resolved = resolve_slice_settings(material)
    process = resolved.get("process", {})

    panel: dict[str, Any] = {
        key: _scalar(process.get(key)) for key in _PANEL_KEYS
    }

    return {
        "material": resolved.get("material", material),
        "profile_ids": resolved.get("profile_ids", {}),
        "settings": panel,
        "counts": {
            "process": len(process),
            "filament": len(resolved.get("filament", {})),
            "printer": len(resolved.get("printer", {})),
        },
    }


def reslice(
    run_root: str | Path,
    overrides: dict[str, Any],
    material: str | None = None,
) -> dict[str, Any]:
    """Re-slice a run's existing mesh with process ``overrides`` applied.

    Runs the pipeline on the existing run layout (no new run folder) feeding the
    primary mesh back in with ``run_slice=True`` and ``process_overrides``.
    Scalar override values are wrapped into Bambu's list-of-strings format. The
    resulting ``.3mf`` ``project_settings.config`` is read back to confirm which
    of the requested keys actually landed.

    Returns ``{run_root, bundle, gcode, sliced, applied}``. Raises
    ``printpipe.pipeline.PipelineError`` on slice failure (carries ``.result``).
    """

    layout = _load_layout(run_root)
    source_mesh = _primary_mesh_path(layout)
    if source_mesh is None:
        raise FileNotFoundError(f"no mesh artifact found for run {layout.run_id}")

    process_overrides = {key: _bambu_value(value) for key, value in overrides.items()}

    kwargs: dict[str, Any] = {
        "source_mesh_path": source_mesh,
        "run_slice": True,
        "process_overrides": process_overrides,
    }
    if material is not None:
        kwargs["material"] = material

    result = run_existing_mesh_pipeline_on_layout(layout, **kwargs)
    result_layout = result.layout

    bundle_path = _first_file(result_layout.bundle_dir, "*.3mf")
    gcode_path = _first_file(result_layout.slice_dir, "*.gcode")
    applied = _read_back_config(bundle_path, overrides.keys()) if bundle_path else {}

    return {
        "run_root": str(result_layout.root),
        "bundle": str(bundle_path) if bundle_path else None,
        "gcode": str(gcode_path) if gcode_path else None,
        "sliced": gcode_path is not None,
        "applied": applied,
    }


def slice_status(run_root: str | Path) -> dict[str, Any]:
    """Report slice state for a run from its slice dir / receipts.

    Returns ``{state, gcode, layers, has_bundle}`` where ``state`` is one of
    ``'idle'`` (never sliced), ``'sliced'`` (gcode present, no errors) or
    ``'failed'`` (slice_result has a non-zero return code or errors).
    """

    layout = _load_layout(run_root)
    gcode_path = _first_file(layout.slice_dir, "*.gcode")
    has_bundle = _first_file(layout.bundle_dir, "*.3mf") is not None

    result = _load_slice_result(layout)
    layers = None
    state = "idle"

    if result is not None:
        layers = result.get("layer_count")
        return_code = result.get("return_code")
        errors = result.get("errors") or []
        if (return_code not in (None, 0)) or errors:
            state = "failed"
        elif gcode_path is not None:
            state = "sliced"
        else:
            state = "failed"
    elif gcode_path is not None:
        state = "sliced"

    return {
        "state": state,
        "gcode": str(gcode_path) if gcode_path else None,
        "layers": layers,
        "has_bundle": has_bundle,
    }


def gcode_stats(gcode_path: str | Path) -> dict[str, Any]:
    """Parse estimated print time and filament usage from a gcode header.

    Reads only the header block (cheap), tolerating a missing file or absent
    fields. Returns ``{print_time, print_time_seconds, filament_g,
    filament_mm, layers}`` with ``None`` for anything not found.
    """

    stats: dict[str, Any] = {
        "print_time": None,
        "print_time_seconds": None,
        "filament_g": None,
        "filament_mm": None,
        "layers": None,
    }

    path = Path(gcode_path)
    if not path.is_file():
        return stats

    header = _read_gcode_header(path)
    for line in header:
        text = line.lstrip(";").strip()

        if stats["print_time"] is None:
            match = re.search(
                r"(?:model printing time|estimated printing time)\s*:\s*"
                r"([0-9hdms ]+?)(?:;|$)",
                text,
                re.IGNORECASE,
            )
            if match:
                stats["print_time"] = match.group(1).strip()
                stats["print_time_seconds"] = _duration_to_seconds(stats["print_time"])

        if stats["filament_g"] is None:
            match = re.search(
                r"total filament weight\s*\[g\]\s*:\s*([\d.,]+)", text, re.IGNORECASE
            )
            if match:
                stats["filament_g"] = _to_float(match.group(1))

        if stats["filament_mm"] is None:
            match = re.search(
                r"total filament length\s*\[mm\]\s*:\s*([\d.,]+)", text, re.IGNORECASE
            )
            if match:
                stats["filament_mm"] = _to_float(match.group(1))

        if stats["layers"] is None:
            match = re.search(r"total layer number\s*:\s*(\d+)", text, re.IGNORECASE)
            if match:
                stats["layers"] = int(match.group(1))

    return stats


# --------------------------------------------------------------------------- #
# internal helpers
# --------------------------------------------------------------------------- #


def _load_layout(run_root: str | Path) -> RunLayout:
    return load_run(run_root)


def _primary_mesh_path(layout: RunLayout) -> Path | None:
    """Pick the best mesh artifact for the viewer, preferring oriented STL."""

    links = discover_run_artifacts(layout.root)
    by_category: dict[str, Path] = {}
    for link in links:
        if link.category in _MESH_CATEGORIES and link.category not in by_category:
            by_category[link.category] = layout.root / link.path

    for category in _MESH_CATEGORIES:
        if category in by_category:
            return by_category[category]

    # Fallback: oriented STL on disk if discovery returned nothing.
    for candidate_dir in (layout.geometry_dir, layout.repair_dir, layout.meshgen_dir):
        candidate = _first_file(candidate_dir, "*.stl")
        if candidate is not None:
            return candidate
    return None


def _first_file(directory: Path, pattern: str) -> Path | None:
    if not directory.is_dir():
        return None
    matches = sorted(
        (path for path in directory.glob(pattern) if path.is_file()),
        key=lambda path: path.as_posix(),
    )
    return matches[0] if matches else None


def _load_slice_result(layout: RunLayout) -> dict[str, Any] | None:
    result_path = layout.slice_dir / "slice_result.json"
    if not result_path.is_file():
        return None
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _scalar(value: Any) -> Any:
    """Coerce a Bambu config value to a single display scalar."""

    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _bambu_value(value: Any) -> Any:
    """Wrap a scalar override into Bambu's list-of-strings format.

    Already-list values pass through (stringified). Booleans become "1"/"0".
    """

    if isinstance(value, (list, tuple)):
        return [_stringify(item) for item in value]
    return [_stringify(value)]


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _read_back_config(bundle_path: Path, keys: Any) -> dict[str, Any]:
    """Read ``project_settings.config`` from a ``.3mf`` for the requested keys."""

    requested = list(keys)
    try:
        with zipfile.ZipFile(bundle_path) as archive:
            config_name = next(
                (name for name in archive.namelist() if name.endswith("project_settings.config")),
                None,
            )
            if config_name is None:
                return {}
            config = json.loads(archive.read(config_name))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return {}

    if not isinstance(config, dict):
        return {}
    return {key: _scalar(config.get(key)) for key in requested if key in config}


def _read_gcode_header(path: Path, max_lines: int = 200) -> list[str]:
    """Return the header comment block (up to the first non-comment / cap)."""

    header: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            if index >= max_lines:
                break
            stripped = line.strip()
            if not stripped:
                continue
            if not stripped.startswith(";"):
                break
            header.append(stripped)
    return header


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _duration_to_seconds(text: str) -> int | None:
    """Convert a Bambu duration like ``2h 11m 15s`` (or ``1d 3h``) to seconds."""

    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    found = False
    for amount, unit in re.findall(r"(\d+)\s*([dhms])", text):
        total += int(amount) * units[unit]
        found = True
    return total if found else None
