from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.threemf import MeshGeometry
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl
from printpipe.geometry import BedSize, candidate_rotations, compute_bounds


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "objects" / "decorative_organic"
STL_PATH = FIXTURE_ROOT / "asymmetric_leaf_shell.stl"
METADATA_PATH = FIXTURE_ROOT / "expected_metadata.json"


def test_decorative_organic_fixture_parses_and_exercises_orientation_candidates():
    assert STL_PATH.stat().st_size < 4_000
    assert b"\0" not in STL_PATH.read_bytes()

    mesh = read_ascii_stl(STL_PATH)

    assert isinstance(mesh, MeshGeometry)
    assert len(mesh.vertices) >= 8
    assert len(mesh.triangles) >= 10

    bounds = compute_bounds(mesh.vertices)
    assert bounds.width_x > bounds.depth_y
    assert bounds.height_z > 8.0
    assert bounds.min_z < 0.0

    candidates = candidate_rotations(mesh.vertices, BedSize(width_mm=80.0, depth_mm=80.0))

    assert [candidate.rotation_degrees for candidate in candidates] == [0.0, 45.0, 90.0, 135.0]
    assert all(candidate.bed_fit is not None for candidate in candidates)
    assert all(candidate.bed_fit.fits for candidate in candidates if candidate.bed_fit is not None)
    assert any(candidate.bounds.min_z == 0.0 for candidate in candidates)


def test_decorative_organic_fixture_metadata_marks_support_risk_as_future_gate():
    assert METADATA_PATH.stat().st_size < 2_000

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    assert metadata["roadmap_item"] == 107
    assert metadata["fixture_name"] == "decorative_organic_asymmetric_leaf_shell"
    assert metadata["requires_future_support_risk_evaluation"] is True
    assert metadata["support_risk"]["evaluation_required"] is True
    assert metadata["support_risk"]["reason"] == "asymmetric overhang-like decorative lobes"
    assert metadata["intended_orientation_notes"] == {
        "visual_orientation_competes_with_printability": True,
        "support_risk_scoring_needed": True,
        "bed_fit_alone_is_insufficient": True,
    }
