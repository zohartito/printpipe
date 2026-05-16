from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.threemf import MeshGeometry
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl
from printpipe.geometry import BedSize, candidate_rotations, compute_bounds, fits_bed
from printpipe.mesh.validate import validate_mesh_topology


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "objects" / "cup_vase"
STL_PATH = FIXTURE_DIR / "cup_vase_open_frustum.stl"
METADATA_PATH = FIXTURE_DIR / "expected_metadata.json"


def test_cup_vase_stl_fixture_is_small_human_readable_ascii():
    text = STL_PATH.read_text(encoding="ascii")

    assert STL_PATH.stat().st_size < 6_000
    assert "\x00" not in text
    assert text.startswith("solid cup_vase_open_frustum\n")
    assert text.endswith("endsolid cup_vase_open_frustum\n")
    assert 12 <= text.count("facet normal") <= 24


def test_cup_vase_stl_parses_to_mesh_geometry_with_open_topology():
    mesh = read_ascii_stl(STL_PATH)
    result = validate_mesh_topology(mesh.triangles, vertices_count=len(mesh.vertices))
    expected = json.loads(METADATA_PATH.read_text(encoding="utf-8"))["expected_topology"]

    assert isinstance(mesh, MeshGeometry)
    assert len(mesh.vertices) == expected["vertices"]
    assert len(mesh.triangles) == expected["triangles"]
    assert result.passed is False
    assert result.stats.watertight is False
    assert result.stats.boundary_edges == expected["boundary_edges"]
    assert result.stats.non_manifold_edges == expected["non_manifold_edges"]
    assert result.diagnostics["inconsistent_winding_edges"] == 0
    assert result.defects == ("6 boundary edges",)


def test_cup_vase_metadata_documents_intended_orientation_notes():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    assert metadata["roadmap_item"] == 105
    assert metadata["source_file"] == STL_PATH.name
    assert metadata["intended_orientation_notes"] == [
        "upright",
        "opening up",
        "base down",
        "cavity/opening detection needed",
    ]
    assert metadata["semantic_orientation"] == {
        "upright_axis": "+Z",
        "opening_direction": "+Z",
        "base_direction": "-Z",
        "requires_cavity_opening_detection": True,
    }


def test_cup_vase_bounds_and_bed_fit_work_for_fixture_geometry():
    mesh = read_ascii_stl(STL_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    bounds = compute_bounds(mesh.vertices)
    bed_fit = fits_bed(bounds, BedSize(width_mm=128.0, depth_mm=128.0, margin_mm=5.0))
    candidates = candidate_rotations(
        mesh.vertices,
        BedSize(width_mm=128.0, depth_mm=128.0, margin_mm=5.0),
        rotations_degrees=(0.0, 90.0),
    )

    assert bounds.extents == tuple(metadata["expected_bounds_mm"]["extents"])
    assert bounds.min_z == 0.0
    assert bounds.max_z == 30.0
    assert bed_fit.fits is True
    assert bed_fit.min_margin_mm == 86.0
    assert [candidate.rotation_degrees for candidate in candidates] == [0.0, 90.0]
    assert all(candidate.bed_fit is not None and candidate.bed_fit.fits for candidate in candidates)
