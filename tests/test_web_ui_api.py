from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.runs import create_run, load_run
from printpipe.web.ui_api import (
    export_run_glb,
    gcode_stats,
    list_settings,
    slice_status,
)

trimesh = pytest.importorskip("trimesh")


def _make_box_run(tmp_path: Path) -> Path:
    """Create a real run folder seeded with a tiny ASCII-STL box mesh."""

    mesh = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    source_stl = tmp_path / "box.stl"
    # PrintPipe uses ASCII STL; force that representation here too.
    source_stl.write_bytes(trimesh.exchange.stl.export_stl_ascii(mesh).encode("utf-8"))

    runs_dir = tmp_path / "runs"
    layout = create_run(source_stl, runs_dir)

    # Mirror what the geometry stage produces so the viewer/export can find it.
    oriented = layout.geometry_dir / "box_oriented.stl"
    oriented.write_bytes(source_stl.read_bytes())
    return layout.root


def test_export_run_glb_writes_loadable_glb(tmp_path: Path):
    run_root = _make_box_run(tmp_path)

    glb_path = export_run_glb(run_root)

    assert glb_path.exists()
    assert glb_path.suffix == ".glb"
    loaded = trimesh.load(glb_path, force="mesh")
    assert loaded.vertices.shape[0] > 0
    assert loaded.faces.shape[0] > 0


def test_export_run_glb_is_cached(tmp_path: Path):
    run_root = _make_box_run(tmp_path)

    first = export_run_glb(run_root)
    first_mtime = first.stat().st_mtime_ns
    second = export_run_glb(run_root)

    assert first == second
    # Cache hit: not re-exported, so mtime is unchanged.
    assert second.stat().st_mtime_ns == first_mtime


def test_export_run_glb_missing_mesh_raises(tmp_path: Path):
    # A run with no mesh artifacts (manifest only, empty stage dirs).
    runs_dir = tmp_path / "runs"
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("a cube\n", encoding="utf-8")
    layout = create_run(prompt, runs_dir)

    with pytest.raises(FileNotFoundError):
        export_run_glb(layout.root)


def test_list_settings_has_expected_keys():
    result = list_settings("Generic PLA")

    assert result["material"] == "Generic PLA"
    assert set(result["counts"]) == {"process", "filament", "printer"}
    assert result["counts"]["process"] > 0

    settings = result["settings"]
    for key in (
        "layer_height",
        "wall_loops",
        "sparse_infill_density",
        "enable_support",
        "support_type",
        "support_style",
        "outer_wall_speed",
    ):
        assert key in settings

    # List-valued config must be coerced to a display scalar.
    assert not isinstance(settings["layer_height"], (list, tuple))
    assert not isinstance(settings["outer_wall_speed"], (list, tuple))


def test_slice_status_idle_when_never_sliced(tmp_path: Path):
    run_root = _make_box_run(tmp_path)

    status = slice_status(run_root)

    assert status["state"] == "idle"
    assert status["gcode"] is None
    assert status["has_bundle"] is False


def test_slice_status_sliced_from_result_json(tmp_path: Path):
    run_root = _make_box_run(tmp_path)
    layout = load_run(run_root)

    gcode = layout.slice_dir / "plate_1.gcode"
    gcode.write_text("; gcode\n", encoding="utf-8")
    (layout.slice_dir / "slice_result.json").write_text(
        json.dumps(
            {"return_code": 0, "errors": [], "layer_count": 235}
        ),
        encoding="utf-8",
    )
    (layout.bundle_dir / "bundle.3mf").write_bytes(b"PK\x03\x04")

    status = slice_status(run_root)

    assert status["state"] == "sliced"
    assert status["layers"] == 235
    assert status["has_bundle"] is True
    assert status["gcode"].endswith("plate_1.gcode")


def test_slice_status_failed_on_nonzero_return_code(tmp_path: Path):
    run_root = _make_box_run(tmp_path)
    layout = load_run(run_root)
    (layout.slice_dir / "slice_result.json").write_text(
        json.dumps({"return_code": 1, "errors": ["boom"], "layer_count": None}),
        encoding="utf-8",
    )

    status = slice_status(run_root)

    assert status["state"] == "failed"


def test_gcode_stats_parses_header(tmp_path: Path):
    gcode = tmp_path / "plate_1.gcode"
    gcode.write_text(
        "; HEADER_BLOCK_START\n"
        "; model printing time: 2h 11m 15s; total estimated time: 2h 11m 35s\n"
        "; total layer number: 235\n"
        "; total filament length [mm] : 20242.85\n"
        "; total filament weight [g] : 50.64\n"
        "; HEADER_BLOCK_END\n"
        "G1 X0 Y0\n",
        encoding="utf-8",
    )

    stats = gcode_stats(gcode)

    assert stats["print_time"] == "2h 11m 15s"
    assert stats["print_time_seconds"] == 2 * 3600 + 11 * 60 + 15
    assert stats["filament_g"] == pytest.approx(50.64)
    assert stats["filament_mm"] == pytest.approx(20242.85)
    assert stats["layers"] == 235


def test_gcode_stats_tolerates_missing_file(tmp_path: Path):
    stats = gcode_stats(tmp_path / "does_not_exist.gcode")

    assert stats == {
        "print_time": None,
        "print_time_seconds": None,
        "filament_g": None,
        "filament_mm": None,
        "layers": None,
    }
