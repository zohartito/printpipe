from __future__ import annotations

import math
import json

from printpipe.contracts import StageStatus
from printpipe.geometry import (
    BedSize,
    candidate_rotations,
    center_xy_drop_z,
    compute_bounds,
    fits_bed,
    likely_flat_base_heuristic,
    rotate_z,
    score_bed_fit_margin,
)
from printpipe.geometry.core import (
    apply_uniform_scale,
    decide_scale_down_or_fail,
    estimate_primary_axes,
    infer_target_scale,
    likely_cavity_opening_heuristic,
    score_support_burden_orientation,
    select_top_orientations,
    write_bed_fit_preview_artifacts,
)


def box_vertices(
    length_x: float,
    depth_y: float,
    height_z: float,
    *,
    z_min: float = 0.0,
) -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 0.0, z_min),
        (length_x, 0.0, z_min),
        (length_x, depth_y, z_min),
        (0.0, depth_y, z_min),
        (0.0, 0.0, z_min + height_z),
        (length_x, 0.0, z_min + height_z),
        (length_x, depth_y, z_min + height_z),
        (0.0, depth_y, z_min + height_z),
    )


def test_rectangular_object_fits_bed_after_45_degree_rotation():
    vertices = box_vertices(300.0, 50.0, 20.0)
    bed = BedSize(width_mm=256.0, depth_mm=256.0)

    axis_aligned = fits_bed(center_xy_drop_z(vertices), bed)
    diagonal = fits_bed(center_xy_drop_z(rotate_z(vertices, 45.0)), bed)

    assert axis_aligned.fits is False
    assert axis_aligned.margin_x_mm == -44.0
    assert diagonal.fits is True
    assert math.isclose(diagonal.bounds.width_x, math.sqrt(2.0) * 175.0)
    assert math.isclose(diagonal.bounds.depth_y, math.sqrt(2.0) * 175.0)
    assert diagonal.min_margin_mm > 8.5

    candidates = candidate_rotations(vertices, bed)
    fit_by_degrees = {
        candidate.rotation_degrees: candidate.bed_fit.fits
        for candidate in candidates
        if candidate.bed_fit is not None
    }

    assert [candidate.rotation_degrees for candidate in candidates] == [
        0.0,
        45.0,
        90.0,
        135.0,
    ]
    assert fit_by_degrees[0.0] is False
    assert fit_by_degrees[45.0] is True
    assert fit_by_degrees[90.0] is False


def test_center_xy_drop_z_centers_footprint_and_places_min_z_on_bed():
    vertices = box_vertices(20.0, 10.0, 7.5, z_min=12.5)

    transformed = center_xy_drop_z(vertices)
    bounds = compute_bounds(transformed)

    assert bounds.min_z == 0.0
    assert bounds.height_z == 7.5
    assert bounds.center_x == 0.0
    assert bounds.center_y == 0.0
    assert transformed[0] == (-10.0, -5.0, 0.0)


def test_score_bed_fit_margin_uses_the_tightest_usable_axis_margin():
    bed = BedSize(width_mm=120.0, depth_mm=100.0, margin_mm=5.0)
    vertices = center_xy_drop_z(box_vertices(100.0, 70.0, 8.0))

    result = fits_bed(vertices, bed)

    assert result.fits is True
    assert result.margin_x_mm == 10.0
    assert result.margin_y_mm == 20.0
    assert result.min_margin_mm == 10.0
    assert result.score == 10.0
    assert score_bed_fit_margin(result) == 10.0


def test_likely_flat_base_heuristic_returns_diagnostic_receipt_not_claim():
    receipt = likely_flat_base_heuristic(
        box_vertices(20.0, 10.0, 5.0),
        tolerance_mm=0.01,
    )

    assert receipt.status is StageStatus.SUCCEEDED
    assert receipt.stage == "geometry.likely_flat_base_heuristic"
    assert receipt.metrics["score"] == 0.5
    assert receipt.metrics["low_z_vertex_fraction"] == 0.5
    assert receipt.metrics["heuristic"] == "low_z_vertex_fraction"


def test_estimate_primary_axes_sorts_bounds_axes_without_semantic_claims():
    estimates = estimate_primary_axes(box_vertices(10.0, 25.0, 5.0))

    assert [estimate.axis for estimate in estimates] == ["y", "x", "z"]
    assert [estimate.length_mm for estimate in estimates] == [25.0, 10.0, 5.0]
    assert estimates[0].unit_vector == (0.0, 1.0, 0.0)
    assert estimates[0].diagnostics["basis"] == "axis_aligned_bounds"


def test_likely_cavity_opening_heuristic_reports_boundary_asymmetry_only():
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (5.0, 5.0, 20.0),
    )

    receipt = likely_cavity_opening_heuristic(vertices, tolerance_mm=0.01)

    assert receipt.status is StageStatus.SUCCEEDED
    assert receipt.stage == "geometry.likely_cavity_opening_heuristic"
    assert receipt.metrics["heuristic"] == "opposite_boundary_vertex_asymmetry"
    assert receipt.metrics["possible_opening"] is True
    assert receipt.metrics["possible_opening_side"] == "z+"
    assert receipt.metrics["score"] == 0.6


def test_support_burden_score_prefers_broader_lower_orientations():
    flat = box_vertices(60.0, 30.0, 6.0)
    upright = box_vertices(6.0, 30.0, 60.0)

    flat_score = score_support_burden_orientation(flat, tolerance_mm=0.01)
    upright_score = score_support_burden_orientation(upright, tolerance_mm=0.01)

    assert flat_score.heuristic == "low_z_contact_fraction_and_height_ratio"
    assert flat_score.score < upright_score.score
    assert flat_score.base_contact_fraction == 0.5
    assert upright_score.height_to_footprint_ratio == 2.0


def test_infer_target_scale_and_apply_uniform_scale_from_bounds():
    vertices = box_vertices(100.0, 40.0, 20.0)

    explicit = infer_target_scale(vertices, target_longest_mm=50.0)
    inferred = infer_target_scale(vertices, bed=BedSize(120.0, 80.0), bed_fill_fraction=0.5)
    scaled = apply_uniform_scale(vertices, explicit.scale_factor)

    assert explicit.reason == "target_longest_mm"
    assert explicit.scale_factor == 0.5
    assert inferred.reason == "bed_fill_fraction"
    assert inferred.target_longest_mm == 40.0
    assert compute_bounds(scaled).extents == (50.0, 20.0, 10.0)


def test_decide_scale_down_or_fail_uses_bed_fit_threshold():
    vertices = box_vertices(300.0, 80.0, 20.0)
    bed = BedSize(200.0, 200.0, margin_mm=10.0)

    allowed = decide_scale_down_or_fail(vertices, bed, min_scale_factor=0.5)
    rejected = decide_scale_down_or_fail(vertices, bed, min_scale_factor=0.8)

    assert allowed.action == "scale_down"
    assert allowed.scale_factor == 0.6
    assert allowed.fits_after is True
    assert rejected.action == "fail"
    assert rejected.scale_factor == 0.6
    assert rejected.fits_after is False


def test_select_top_orientations_and_write_bed_fit_preview_artifacts(tmp_path):
    vertices = box_vertices(300.0, 50.0, 20.0)
    bed = BedSize(256.0, 256.0)
    candidates = candidate_rotations(
        vertices,
        bed,
        rotations_degrees=(0.0, 45.0, 90.0, 135.0),
    )

    selected = select_top_orientations(candidates)
    receipt = write_bed_fit_preview_artifacts(
        selected[0],
        bed,
        tmp_path,
        stem="bed-fit",
    )

    assert [candidate.rotation_degrees for candidate in selected] == [45.0, 135.0, 0.0]
    assert receipt.status is StageStatus.SUCCEEDED
    assert {artifact.path.name for artifact in receipt.artifacts} == {
        "bed-fit.svg",
        "bed-fit.json",
    }

    svg_path = tmp_path / "bed-fit.svg"
    json_path = tmp_path / "bed-fit.json"
    assert "<svg" in svg_path.read_text()
    preview = json.loads(json_path.read_text())
    assert preview["fit"]["fits"] is True
    assert preview["orientation"]["rotation_degrees"] == 45.0
    assert preview["heuristics"]["basis"] == "bounds_only"
