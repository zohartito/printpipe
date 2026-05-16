"""Geometry orientation and bed-fit helpers for PrintPipe."""

from __future__ import annotations

from printpipe.geometry.core import (
    DEFAULT_ROTATIONS_DEGREES,
    BedFitResult,
    BedSize,
    Bounds3D,
    OrientationCandidate,
    candidate_rotations,
    center_xy_drop_z,
    compute_bounds,
    fits_bed,
    likely_flat_base_heuristic,
    rotate_z,
    score_bed_fit_margin,
)

__all__ = [
    "DEFAULT_ROTATIONS_DEGREES",
    "BedFitResult",
    "BedSize",
    "Bounds3D",
    "OrientationCandidate",
    "candidate_rotations",
    "center_xy_drop_z",
    "compute_bounds",
    "fits_bed",
    "likely_flat_base_heuristic",
    "rotate_z",
    "score_bed_fit_margin",
]
