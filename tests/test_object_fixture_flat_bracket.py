from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.threemf import MeshGeometry
from printpipe.bambu.threemf.mesh_adapter import read_ascii_stl
from printpipe.geometry import BedSize, candidate_rotations, compute_bounds


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "objects" / "flat_bracket"
STL_PATH = FIXTURE_ROOT / "flat_bracket.stl"
EXPECTED_PATH = FIXTURE_ROOT / "expected_metadata.json"


def load_expected_metadata() -> dict[str, object]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def test_flat_bracket_ascii_stl_is_small_parseable_mesh_geometry():
    mesh = read_ascii_stl(STL_PATH)

    assert STL_PATH.stat().st_size < 8_000
    assert isinstance(mesh, MeshGeometry)
    assert len(mesh.vertices) >= 8
    assert len(mesh.triangles) >= 12


def test_flat_bracket_metadata_records_orientation_intent():
    expected = load_expected_metadata()
    intended_orientation = expected["intended_orientation"]

    assert expected["roadmap_item"] == 106
    assert intended_orientation["flattest_face_down"] is True
    assert intended_orientation["long_axis_can_rotate_for_bed_fit"] is True
    assert (
        intended_orientation["semantic_understanding_priority"]
        == "less_critical_than_bed_fit_scoring"
    )


def test_flat_bracket_is_flat_and_has_a_45_degree_bed_fit_candidate():
    expected = load_expected_metadata()
    bed_fit = expected["bed_fit_test"]
    mesh = read_ascii_stl(STL_PATH)
    bounds = compute_bounds(mesh.vertices)

    longest_axis_mm = max(bounds.width_x, bounds.depth_y)
    assert bounds.height_z <= longest_axis_mm * expected["max_height_to_length_ratio"]

    bed = BedSize(
        width_mm=bed_fit["bed_width_mm"],
        depth_mm=bed_fit["bed_depth_mm"],
    )
    candidates = candidate_rotations(
        mesh.vertices,
        bed,
        rotations_degrees=bed_fit["rotations_degrees"],
    )
    fit_by_rotation = {
        candidate.rotation_degrees: candidate.bed_fit.fits
        for candidate in candidates
        if candidate.bed_fit is not None
    }

    assert fit_by_rotation[0.0] is False
    assert fit_by_rotation[45.0] is True
