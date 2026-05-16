"""Dependency-light geometry helpers for orientation and bed-fit checks."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from printpipe.contracts import StageReceipt, StageStatus


Vertex3D = tuple[float, float, float]
DEFAULT_ROTATIONS_DEGREES = (0.0, 45.0, 90.0, 135.0)


@dataclass(frozen=True)
class Bounds3D:
    """Axis-aligned 3D bounds in millimeters."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x:
            raise ValueError("max_x must be greater than or equal to min_x")
        if self.max_y < self.min_y:
            raise ValueError("max_y must be greater than or equal to min_y")
        if self.max_z < self.min_z:
            raise ValueError("max_z must be greater than or equal to min_z")

    @property
    def width_x(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth_y(self) -> float:
        return self.max_y - self.min_y

    @property
    def height_z(self) -> float:
        return self.max_z - self.min_z

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    @property
    def center_z(self) -> float:
        return (self.min_z + self.max_z) / 2.0

    @property
    def extents(self) -> tuple[float, float, float]:
        return (self.width_x, self.depth_y, self.height_z)


@dataclass(frozen=True)
class BedSize:
    """Printable bed dimensions in millimeters."""

    width_mm: float
    depth_mm: float
    margin_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError("width_mm must be positive")
        if self.depth_mm <= 0:
            raise ValueError("depth_mm must be positive")
        if self.margin_mm < 0:
            raise ValueError("margin_mm must be non-negative")

    @property
    def usable_width_mm(self) -> float:
        return self.width_mm - (2.0 * self.margin_mm)

    @property
    def usable_depth_mm(self) -> float:
        return self.depth_mm - (2.0 * self.margin_mm)


@dataclass(frozen=True)
class BedFitResult:
    """Bed-fit metrics for a bounded orientation."""

    fits: bool
    bounds: Bounds3D
    bed: BedSize
    margin_x_mm: float
    margin_y_mm: float
    min_margin_mm: float
    overflow_x_mm: float
    overflow_y_mm: float
    score: float
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrientationCandidate:
    """One Z-rotation candidate with optional bed-fit scoring."""

    rotation_degrees: float
    vertices: tuple[Vertex3D, ...]
    bounds: Bounds3D
    bed_fit: BedFitResult | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        if self.bed_fit is None:
            return 0.0
        return self.bed_fit.score


def compute_bounds(vertices: Iterable[Sequence[float]]) -> Bounds3D:
    """Compute axis-aligned bounds for vertex triples."""
    normalized = _normalize_vertices(vertices)
    if not normalized:
        raise ValueError("at least one vertex is required to compute bounds")

    first_x, first_y, first_z = normalized[0]
    min_x = max_x = first_x
    min_y = max_y = first_y
    min_z = max_z = first_z

    for x, y, z in normalized[1:]:
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        min_z = min(min_z, z)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        max_z = max(max_z, z)

    return Bounds3D(
        min_x=min_x,
        min_y=min_y,
        min_z=min_z,
        max_x=max_x,
        max_y=max_y,
        max_z=max_z,
    )


def center_xy_drop_z(vertices: Iterable[Sequence[float]]) -> tuple[Vertex3D, ...]:
    """Center an object in XY and translate it so its minimum Z is zero."""
    normalized = _normalize_vertices(vertices)
    bounds = compute_bounds(normalized)
    return tuple(
        (
            _clean_float(x - bounds.center_x),
            _clean_float(y - bounds.center_y),
            _clean_float(z - bounds.min_z),
        )
        for x, y, z in normalized
    )


def rotate_z(
    vertices: Iterable[Sequence[float]],
    degrees: float,
) -> tuple[Vertex3D, ...]:
    """Rotate vertices around the Z axis by degrees, about the origin."""
    normalized = _normalize_vertices(vertices)
    radians = math.radians(degrees)
    cos_theta = math.cos(radians)
    sin_theta = math.sin(radians)

    return tuple(
        (
            _clean_float((x * cos_theta) - (y * sin_theta)),
            _clean_float((x * sin_theta) + (y * cos_theta)),
            z,
        )
        for x, y, z in normalized
    )


def fits_bed(
    bounds_or_vertices: Bounds3D | Iterable[Sequence[float]],
    bed: BedSize,
) -> BedFitResult:
    """Return bed-fit metrics for bounds or vertices."""
    bounds = _coerce_bounds(bounds_or_vertices)
    margin_x = bed.usable_width_mm - bounds.width_x
    margin_y = bed.usable_depth_mm - bounds.depth_y
    min_margin = min(margin_x, margin_y)
    overflow_x = max(0.0, -margin_x)
    overflow_y = max(0.0, -margin_y)
    fits = margin_x >= 0.0 and margin_y >= 0.0
    score = score_bed_fit_margin(bounds, bed)

    return BedFitResult(
        fits=fits,
        bounds=bounds,
        bed=bed,
        margin_x_mm=_clean_float(margin_x),
        margin_y_mm=_clean_float(margin_y),
        min_margin_mm=_clean_float(min_margin),
        overflow_x_mm=_clean_float(overflow_x),
        overflow_y_mm=_clean_float(overflow_y),
        score=_clean_float(score),
        diagnostics={
            "usable_width_mm": bed.usable_width_mm,
            "usable_depth_mm": bed.usable_depth_mm,
            "footprint_mm": (bounds.width_x, bounds.depth_y),
        },
    )


def score_bed_fit_margin(
    bed_fit_or_bounds: BedFitResult | Bounds3D | Iterable[Sequence[float]],
    bed: BedSize | None = None,
) -> float:
    """Score bed fit by the tightest remaining usable-axis margin in mm."""
    if isinstance(bed_fit_or_bounds, BedFitResult):
        return bed_fit_or_bounds.min_margin_mm
    if bed is None:
        raise TypeError("bed is required when scoring bounds or vertices")

    bounds = _coerce_bounds(bed_fit_or_bounds)
    margin_x = bed.usable_width_mm - bounds.width_x
    margin_y = bed.usable_depth_mm - bounds.depth_y
    return _clean_float(min(margin_x, margin_y))


def candidate_rotations(
    vertices: Iterable[Sequence[float]],
    bed: BedSize | None = None,
    *,
    rotations_degrees: Iterable[float] = DEFAULT_ROTATIONS_DEGREES,
) -> tuple[OrientationCandidate, ...]:
    """Generate centered, bed-dropped Z-rotation candidates."""
    normalized = _normalize_vertices(vertices)
    candidates: list[OrientationCandidate] = []

    for degrees in rotations_degrees:
        rotation_degrees = float(degrees)
        transformed = center_xy_drop_z(rotate_z(normalized, rotation_degrees))
        bounds = compute_bounds(transformed)
        bed_fit = fits_bed(bounds, bed) if bed is not None else None
        candidates.append(
            OrientationCandidate(
                rotation_degrees=_clean_float(rotation_degrees),
                vertices=transformed,
                bounds=bounds,
                bed_fit=bed_fit,
                diagnostics={
                    "rotation_axis": "z",
                    "transform_order": "rotate_z_then_center_xy_drop_z",
                },
            )
        )

    return tuple(candidates)


def likely_flat_base_heuristic(
    vertices: Iterable[Sequence[float]],
    *,
    tolerance_mm: float = 0.25,
) -> StageReceipt:
    """Return a diagnostic low-Z concentration score without semantic claims."""
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm must be non-negative")

    normalized = _normalize_vertices(vertices)
    if not normalized:
        return StageReceipt(
            stage="geometry.likely_flat_base_heuristic",
            status=StageStatus.FAILED,
            message="no vertices available for geometry heuristic",
            metrics={
                "score": 0.0,
                "heuristic": "low_z_vertex_fraction",
                "tolerance_mm": tolerance_mm,
            },
        )

    bounds = compute_bounds(normalized)
    low_z_count = sum(1 for _, _, z in normalized if z <= bounds.min_z + tolerance_mm)
    fraction = low_z_count / len(normalized)

    return StageReceipt(
        stage="geometry.likely_flat_base_heuristic",
        status=StageStatus.SUCCEEDED,
        message="computed low-Z vertex concentration diagnostic",
        metrics={
            "score": _clean_float(fraction),
            "heuristic": "low_z_vertex_fraction",
            "low_z_vertex_count": low_z_count,
            "total_vertices": len(normalized),
            "low_z_vertex_fraction": _clean_float(fraction),
            "min_z_mm": bounds.min_z,
            "tolerance_mm": tolerance_mm,
        },
    )


def _coerce_bounds(
    bounds_or_vertices: Bounds3D | Iterable[Sequence[float]],
) -> Bounds3D:
    if isinstance(bounds_or_vertices, Bounds3D):
        return bounds_or_vertices
    return compute_bounds(bounds_or_vertices)


def _normalize_vertices(vertices: Iterable[Sequence[float]]) -> tuple[Vertex3D, ...]:
    normalized: list[Vertex3D] = []
    for vertex in vertices:
        if len(vertex) != 3:
            raise ValueError(f"vertices must be triples, got {vertex!r}")
        x, y, z = vertex
        normalized.append((float(x), float(y), float(z)))
    return tuple(normalized)


def _clean_float(value: float) -> float:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return 0.0
    nearest_int = round(value)
    if math.isclose(value, nearest_int, abs_tol=1e-12):
        return float(nearest_int)
    return value
