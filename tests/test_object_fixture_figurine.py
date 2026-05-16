from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.threemf import MeshGeometry
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl
from printpipe.geometry import BedSize, candidate_rotations, compute_bounds


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "objects" / "figurine"
STL_PATH = FIXTURE_ROOT / "simple_figurine_ascii.stl"
METADATA_PATH = FIXTURE_ROOT / "expected_metadata.json"


def test_figurine_ascii_stl_fixture_parses_to_mesh_geometry():
    assert STL_PATH.exists()
    assert STL_PATH.stat().st_size < 8_000

    mesh = read_ascii_stl(STL_PATH)
    bounds = compute_bounds(mesh.vertices)

    assert isinstance(mesh, MeshGeometry)
    assert len(mesh.vertices) >= 12
    assert len(mesh.triangles) >= 12
    assert bounds.min_z == 0.0
    assert bounds.height_z > bounds.width_x
    assert bounds.height_z > bounds.depth_y


def test_figurine_expected_metadata_records_semantic_orientation_notes():
    assert METADATA_PATH.exists()
    assert METADATA_PATH.stat().st_size < 2_000

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    orientation = metadata["intended_orientation"]

    assert metadata["roadmap_item"] == 104
    assert metadata["source_mesh"] == STL_PATH.name
    assert orientation["upright"] is True
    assert orientation["base_down"] is True
    assert orientation["semantic_orientation_required"] is True
    assert any("PCA" in note for note in orientation["notes"])
    assert any("base down" in note.lower() for note in orientation["notes"])


def test_figurine_candidate_bed_fit_scoring_runs_for_default_rotations():
    mesh = read_ascii_stl(STL_PATH)
    bed = BedSize(width_mm=256.0, depth_mm=256.0)

    candidates = candidate_rotations(mesh.vertices, bed)

    assert [candidate.rotation_degrees for candidate in candidates] == [0.0, 45.0, 90.0, 135.0]
    assert all(candidate.bed_fit is not None for candidate in candidates)
    assert all(candidate.bed_fit.fits for candidate in candidates if candidate.bed_fit is not None)
    assert all(isinstance(candidate.score, float) for candidate in candidates)
