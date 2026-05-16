from __future__ import annotations

import math

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
