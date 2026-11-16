"""Dependency-light geometry helpers for orientation and bed-fit checks."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus


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
    height_mm: float | None = None

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError("width_mm must be positive")
        if self.depth_mm <= 0:
            raise ValueError("depth_mm must be positive")
        if self.height_mm is not None and self.height_mm <= 0:
            raise ValueError("height_mm must be positive")
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


@dataclass(frozen=True)
class AxisEstimate:
    """A bounds-only estimate of one model axis."""

    axis: str
    length_mm: float
    rank: int
    unit_vector: Vertex3D
    normalized_length: float
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupportBurdenScore:
    """Bounds/vertex-only support burden proxy; lower score is better."""

    score: float
    base_contact_fraction: float
    height_to_footprint_ratio: float
    heuristic: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScalePlan:
    """Uniform scale inferred from an explicit target or bed envelope."""

    scale_factor: float
    source_longest_mm: float
    target_longest_mm: float
    reason: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScaleDownDecision:
    """Decision for oversized geometry: keep, scale down, or fail."""

    action: str
    scale_factor: float
    fits_after: bool
    reason: str
    bounds: Bounds3D
    scaled_bounds: Bounds3D
    bed_fit: BedFitResult
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


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
    fits = (margin_x >= 0.0 and margin_y >= 0.0
            and (bed.height_mm is None or bounds.height_z <= bed.height_mm))
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


def estimate_primary_axes(
    bounds_or_vertices: Bounds3D | Iterable[Sequence[float]],
) -> tuple[AxisEstimate, ...]:
    """Estimate primary axes from axis-aligned bounds only."""
    bounds = _coerce_bounds(bounds_or_vertices)
    axis_rows = (
        ("x", bounds.width_x, (1.0, 0.0, 0.0)),
        ("y", bounds.depth_y, (0.0, 1.0, 0.0)),
        ("z", bounds.height_z, (0.0, 0.0, 1.0)),
    )
    longest = max(length for _, length, _ in axis_rows)
    ranked = sorted(axis_rows, key=lambda row: (-row[1], row[0]))

    return tuple(
        AxisEstimate(
            axis=axis,
            length_mm=_clean_float(length),
            rank=rank,
            unit_vector=unit_vector,
            normalized_length=_clean_float(length / longest) if longest > 0.0 else 0.0,
            diagnostics={
                "basis": "axis_aligned_bounds",
                "semantic_claim": False,
            },
        )
        for rank, (axis, length, unit_vector) in enumerate(ranked, start=1)
    )


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


def likely_cavity_opening_heuristic(
    vertices: Iterable[Sequence[float]],
    *,
    tolerance_mm: float = 0.25,
    asymmetry_threshold: float = 0.25,
) -> StageReceipt:
    """Return a diagnostic boundary-vertex asymmetry score, not a vision claim."""
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm must be non-negative")
    if asymmetry_threshold < 0:
        raise ValueError("asymmetry_threshold must be non-negative")

    normalized = _normalize_vertices(vertices)
    if not normalized:
        return StageReceipt(
            stage="geometry.likely_cavity_opening_heuristic",
            status=StageStatus.FAILED,
            message="no vertices available for cavity/opening heuristic",
            metrics={
                "score": 0.0,
                "heuristic": "opposite_boundary_vertex_asymmetry",
                "tolerance_mm": tolerance_mm,
                "asymmetry_threshold": asymmetry_threshold,
            },
        )

    bounds = compute_bounds(normalized)
    side_counts = {
        "x-": sum(1 for x, _, _ in normalized if x <= bounds.min_x + tolerance_mm),
        "x+": sum(1 for x, _, _ in normalized if x >= bounds.max_x - tolerance_mm),
        "y-": sum(1 for _, y, _ in normalized if y <= bounds.min_y + tolerance_mm),
        "y+": sum(1 for _, y, _ in normalized if y >= bounds.max_y - tolerance_mm),
        "z-": sum(1 for _, _, z in normalized if z <= bounds.min_z + tolerance_mm),
        "z+": sum(1 for _, _, z in normalized if z >= bounds.max_z - tolerance_mm),
    }
    side_pairs = (("x", "x-", "x+"), ("y", "y-", "y+"), ("z", "z-", "z+"))
    best_axis = "x"
    best_side = "x-"
    best_low_count = side_counts["x-"]
    best_high_count = side_counts["x+"]
    best_score = -1.0

    for axis, negative_side, positive_side in side_pairs:
        negative_count = side_counts[negative_side]
        positive_count = side_counts[positive_side]
        low_side = negative_side if negative_count <= positive_count else positive_side
        low_count = min(negative_count, positive_count)
        high_count = max(negative_count, positive_count)
        score = abs(negative_count - positive_count) / len(normalized)
        if score > best_score:
            best_axis = axis
            best_side = low_side
            best_low_count = low_count
            best_high_count = high_count
            best_score = score

    possible_opening = best_score >= asymmetry_threshold and best_high_count > 0

    return StageReceipt(
        stage="geometry.likely_cavity_opening_heuristic",
        status=StageStatus.SUCCEEDED,
        message="computed boundary-vertex asymmetry diagnostic",
        metrics={
            "score": _clean_float(best_score),
            "heuristic": "opposite_boundary_vertex_asymmetry",
            "possible_opening": possible_opening,
            "possible_opening_axis": best_axis,
            "possible_opening_side": best_side,
            "sparser_side_vertex_count": best_low_count,
            "opposite_side_vertex_count": best_high_count,
            "side_vertex_counts": side_counts,
            "total_vertices": len(normalized),
            "tolerance_mm": tolerance_mm,
            "asymmetry_threshold": asymmetry_threshold,
            "semantic_claim": False,
        },
    )


def score_support_burden_orientation(
    vertices_or_candidate: OrientationCandidate | Iterable[Sequence[float]],
    *,
    tolerance_mm: float = 0.25,
) -> SupportBurdenScore:
    """Score an orientation using only low-Z concentration and bounds shape."""
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm must be non-negative")

    if isinstance(vertices_or_candidate, OrientationCandidate):
        normalized = vertices_or_candidate.vertices
    else:
        normalized = _normalize_vertices(vertices_or_candidate)
    if not normalized:
        raise ValueError("at least one vertex is required to score support burden")

    bounds = compute_bounds(normalized)
    low_z_count = sum(1 for _, _, z in normalized if z <= bounds.min_z + tolerance_mm)
    base_contact_fraction = low_z_count / len(normalized)
    footprint_reference = max(bounds.width_x, bounds.depth_y)
    if footprint_reference <= 0.0:
        height_to_footprint_ratio = bounds.height_z
    else:
        height_to_footprint_ratio = bounds.height_z / footprint_reference
    height_penalty = min(height_to_footprint_ratio, 10.0) * 0.1
    score = (1.0 - base_contact_fraction) + height_penalty

    return SupportBurdenScore(
        score=_clean_float(score),
        base_contact_fraction=_clean_float(base_contact_fraction),
        height_to_footprint_ratio=_clean_float(height_to_footprint_ratio),
        heuristic="low_z_contact_fraction_and_height_ratio",
        diagnostics={
            "basis": "bounds_only_vertices_only",
            "lower_is_better": True,
            "low_z_vertex_count": low_z_count,
            "total_vertices": len(normalized),
            "tolerance_mm": tolerance_mm,
            "height_penalty": _clean_float(height_penalty),
            "semantic_claim": False,
        },
    )


def infer_target_scale(
    bounds_or_vertices: Bounds3D | Iterable[Sequence[float]],
    *,
    target_longest_mm: float | None = None,
    target_height_mm: float | None = None,
    bed: BedSize | None = None,
    bed_fill_fraction: float = 0.9,
) -> ScalePlan:
    """Infer a uniform scale from a target dimension or bed fill fraction."""
    if target_longest_mm is not None and target_height_mm is not None:
        raise ValueError("provide only one target dimension")
    if target_longest_mm is not None and target_longest_mm <= 0.0:
        raise ValueError("target_longest_mm must be positive")
    if target_height_mm is not None and target_height_mm <= 0.0:
        raise ValueError("target_height_mm must be positive")
    if bed_fill_fraction <= 0.0 or bed_fill_fraction > 1.0:
        raise ValueError("bed_fill_fraction must be greater than 0 and at most 1")

    bounds = _coerce_bounds(bounds_or_vertices)
    source_longest = max(bounds.extents)
    if source_longest <= 0.0:
        raise ValueError("source geometry must have at least one positive extent")

    if target_longest_mm is not None:
        target_longest = target_longest_mm
        scale_factor = target_longest / source_longest
        reason = "target_longest_mm"
    elif target_height_mm is not None:
        if bounds.height_z <= 0.0:
            raise ValueError("source geometry height must be positive")
        scale_factor = target_height_mm / bounds.height_z
        target_longest = source_longest * scale_factor
        reason = "target_height_mm"
    elif bed is not None:
        target_longest = min(bed.usable_width_mm, bed.usable_depth_mm) * bed_fill_fraction
        if target_longest <= 0.0:
            raise ValueError("bed usable dimensions must be positive")
        scale_factor = target_longest / source_longest
        reason = "bed_fill_fraction"
    else:
        target_longest = source_longest
        scale_factor = 1.0
        reason = "preserve_source_size"

    return ScalePlan(
        scale_factor=_clean_float(scale_factor),
        source_longest_mm=_clean_float(source_longest),
        target_longest_mm=_clean_float(target_longest),
        reason=reason,
        diagnostics={
            "basis": "axis_aligned_bounds",
            "bed_fill_fraction": bed_fill_fraction,
            "semantic_claim": False,
        },
    )


def apply_uniform_scale(
    vertices: Iterable[Sequence[float]],
    scale_factor: float,
) -> tuple[Vertex3D, ...]:
    """Apply a uniform scale to vertices."""
    if scale_factor <= 0.0:
        raise ValueError("scale_factor must be positive")
    normalized = _normalize_vertices(vertices)
    return tuple(
        (
            _clean_float(x * scale_factor),
            _clean_float(y * scale_factor),
            _clean_float(z * scale_factor),
        )
        for x, y, z in normalized
    )


def decide_scale_down_or_fail(
    bounds_or_vertices: Bounds3D | Iterable[Sequence[float]],
    bed: BedSize,
    *,
    min_scale_factor: float = 0.5,
) -> ScaleDownDecision:
    """Decide whether oversized geometry may be uniformly scaled to the bed."""
    if min_scale_factor <= 0.0 or min_scale_factor > 1.0:
        raise ValueError("min_scale_factor must be greater than 0 and at most 1")

    bounds = _coerce_bounds(bounds_or_vertices)
    current_fit = fits_bed(bounds, bed)
    if current_fit.fits:
        return ScaleDownDecision(
            action="keep",
            scale_factor=1.0,
            fits_after=True,
            reason="already_fits_bed",
            bounds=bounds,
            scaled_bounds=bounds,
            bed_fit=current_fit,
            diagnostics={"required_scale_factor": 1.0},
        )

    scale_x = bed.usable_width_mm / bounds.width_x if bounds.width_x > 0.0 else math.inf
    scale_y = bed.usable_depth_mm / bounds.depth_y if bounds.depth_y > 0.0 else math.inf
    required_scale = _clean_float(min(1.0, scale_x, scale_y))
    scaled_bounds = _scale_bounds(bounds, required_scale)
    scaled_fit = fits_bed(scaled_bounds, bed)
    can_scale = required_scale >= min_scale_factor and scaled_fit.fits
    action = "scale_down" if can_scale else "fail"

    return ScaleDownDecision(
        action=action,
        scale_factor=required_scale,
        fits_after=can_scale,
        reason=(
            "scale_down_within_allowed_threshold"
            if can_scale
            else "required_scale_below_allowed_threshold"
        ),
        bounds=bounds,
        scaled_bounds=scaled_bounds,
        bed_fit=scaled_fit,
        diagnostics={
            "min_scale_factor": min_scale_factor,
            "required_scale_factor": required_scale,
            "original_fit": current_fit.fits,
        },
    )


def select_top_orientations(
    candidates: Iterable[OrientationCandidate],
    *,
    limit: int = 3,
    require_bed_fit: bool = False,
    support_weight: float = 10.0,
) -> tuple[OrientationCandidate, ...]:
    """Select the best orientation candidates by bed margin and support proxy."""
    if limit <= 0:
        return ()
    if support_weight < 0.0:
        raise ValueError("support_weight must be non-negative")

    scored: list[tuple[float, float, float, float, OrientationCandidate]] = []
    for candidate in candidates:
        if require_bed_fit and (candidate.bed_fit is None or not candidate.bed_fit.fits):
            continue
        bed_score = candidate.bed_fit.score if candidate.bed_fit is not None else 0.0
        support_score = score_support_burden_orientation(candidate).score
        combined_score = bed_score - (support_score * support_weight)
        scored.append(
            (
                combined_score,
                bed_score,
                -support_score,
                -candidate.rotation_degrees,
                candidate,
            )
        )

    scored.sort(key=lambda row: (row[0], row[1], row[2], row[3]), reverse=True)
    return tuple(row[4] for row in scored[:limit])


def write_bed_fit_preview_artifacts(
    candidate_or_bounds: OrientationCandidate | Bounds3D | Iterable[Sequence[float]],
    bed: BedSize,
    output_dir: str | Path,
    *,
    stem: str = "bed_fit",
) -> StageReceipt:
    """Write dependency-free SVG and JSON bed-fit preview artifacts."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    svg_path = output_path / f"{stem}.svg"
    json_path = output_path / f"{stem}.json"

    if isinstance(candidate_or_bounds, OrientationCandidate):
        bounds = candidate_or_bounds.bounds
        rotation_degrees = candidate_or_bounds.rotation_degrees
    else:
        bounds = _coerce_bounds(candidate_or_bounds)
        rotation_degrees = None
    bed_fit = fits_bed(bounds, bed)
    payload = {
        "bed": _bed_to_dict(bed),
        "bounds": _bounds_to_dict(bounds),
        "fit": _bed_fit_to_dict(bed_fit),
        "orientation": {"rotation_degrees": rotation_degrees},
        "heuristics": {
            "basis": "bounds_only",
            "semantic_claim": False,
        },
    }

    svg_path.write_text(_render_bed_fit_svg(bounds, bed, bed_fit), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return StageReceipt(
        stage="geometry.write_bed_fit_preview_artifacts",
        status=StageStatus.SUCCEEDED,
        message="wrote bounds-only bed-fit preview artifacts",
        artifacts=(
            Artifact(
                kind=ArtifactKind.PREVIEW,
                path=svg_path,
                label="Bed fit SVG preview",
                metadata={"format": "svg"},
            ),
            Artifact(
                kind=ArtifactKind.REPORT,
                path=json_path,
                label="Bed fit preview JSON",
                metadata={"format": "json"},
            ),
        ),
        metrics={
            "fits": bed_fit.fits,
            "min_margin_mm": bed_fit.min_margin_mm,
            "rotation_degrees": rotation_degrees,
            "basis": "bounds_only",
        },
    )


def write_run_detail_model_preview_artifacts(
    candidate_or_bounds: OrientationCandidate | Bounds3D | Iterable[Sequence[float]],
    bed: BedSize,
    output_dir: str | Path,
    *,
    stem: str = "run_detail_model_preview",
) -> StageReceipt:
    """Write a deterministic bounds-only model preview for run-detail UI."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    svg_path = output_path / f"{stem}.svg"
    json_path = output_path / f"{stem}.json"

    if isinstance(candidate_or_bounds, OrientationCandidate):
        bounds = candidate_or_bounds.bounds
        rotation_degrees = candidate_or_bounds.rotation_degrees
    else:
        bounds = _coerce_bounds(candidate_or_bounds)
        rotation_degrees = None
    bed_fit = fits_bed(bounds, bed)
    payload = {
        "bed": _bed_to_dict(bed),
        "bounds": _bounds_to_dict(bounds),
        "fit": _bed_fit_to_dict(bed_fit),
        "orientation": {"rotation_degrees": rotation_degrees},
        "preview": {
            "kind": "run_detail_model_preview",
            "projection": "bounds_only_isometric",
        },
        "heuristics": {
            "basis": "bounds_only",
            "semantic_claim": False,
        },
    }

    svg_path.write_text(_render_run_detail_model_svg(bounds, bed, bed_fit), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return StageReceipt(
        stage="geometry.write_run_detail_model_preview_artifacts",
        status=StageStatus.SUCCEEDED,
        message="wrote deterministic run-detail model preview artifacts",
        artifacts=(
            Artifact(
                kind=ArtifactKind.PREVIEW,
                path=svg_path,
                label="Run detail model SVG preview",
                metadata={"format": "svg", "projection": "bounds_only_isometric"},
            ),
            Artifact(
                kind=ArtifactKind.REPORT,
                path=json_path,
                label="Run detail model preview JSON",
                metadata={"format": "json"},
            ),
        ),
        metrics={
            "fits": bed_fit.fits,
            "bounds_mm": bounds.extents,
            "min_margin_mm": bed_fit.min_margin_mm,
            "rotation_degrees": rotation_degrees,
            "basis": "bounds_only",
            "semantic_claim": False,
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


def _scale_bounds(bounds: Bounds3D, scale_factor: float) -> Bounds3D:
    return Bounds3D(
        min_x=_clean_float(bounds.min_x * scale_factor),
        min_y=_clean_float(bounds.min_y * scale_factor),
        min_z=_clean_float(bounds.min_z * scale_factor),
        max_x=_clean_float(bounds.max_x * scale_factor),
        max_y=_clean_float(bounds.max_y * scale_factor),
        max_z=_clean_float(bounds.max_z * scale_factor),
    )


def _bounds_to_dict(bounds: Bounds3D) -> dict[str, float]:
    return {
        "min_x": bounds.min_x,
        "min_y": bounds.min_y,
        "min_z": bounds.min_z,
        "max_x": bounds.max_x,
        "max_y": bounds.max_y,
        "max_z": bounds.max_z,
        "width_x": bounds.width_x,
        "depth_y": bounds.depth_y,
        "height_z": bounds.height_z,
    }


def _bed_to_dict(bed: BedSize) -> dict[str, float]:
    return {
        "width_mm": bed.width_mm,
        "depth_mm": bed.depth_mm,
        "margin_mm": bed.margin_mm,
        "height_mm": bed.height_mm,
        "usable_width_mm": bed.usable_width_mm,
        "usable_depth_mm": bed.usable_depth_mm,
    }


def _bed_fit_to_dict(bed_fit: BedFitResult) -> dict[str, Any]:
    return {
        "fits": bed_fit.fits,
        "margin_x_mm": bed_fit.margin_x_mm,
        "margin_y_mm": bed_fit.margin_y_mm,
        "min_margin_mm": bed_fit.min_margin_mm,
        "overflow_x_mm": bed_fit.overflow_x_mm,
        "overflow_y_mm": bed_fit.overflow_y_mm,
        "overflow_z_mm": max(0.0, bed_fit.bounds.height_z - bed_fit.bed.height_mm)
        if bed_fit.bed.height_mm is not None else 0.0,
        "score": bed_fit.score,
    }


def _render_bed_fit_svg(bounds: Bounds3D, bed: BedSize, bed_fit: BedFitResult) -> str:
    bed_width = _svg_float(bed.width_mm)
    bed_depth = _svg_float(bed.depth_mm)
    usable_width = _svg_float(max(0.0, bed.usable_width_mm))
    usable_depth = _svg_float(max(0.0, bed.usable_depth_mm))
    margin = _svg_float(bed.margin_mm)
    part_x = _svg_float((bed.width_mm - bounds.width_x) / 2.0)
    part_y = _svg_float((bed.depth_mm - bounds.depth_y) / 2.0)
    part_width = _svg_float(bounds.width_x)
    part_depth = _svg_float(bounds.depth_y)
    part_fill = "#22c55e" if bed_fit.fits else "#ef4444"
    part_stroke = "#15803d" if bed_fit.fits else "#b91c1c"

    return "\n".join(
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {bed_width} {bed_depth}" width="512" height="512" '
            'role="img" aria-labelledby="title desc">',
            "  <title id=\"title\">Bed fit preview</title>",
            "  <desc id=\"desc\">Bounds-only footprint preview centered on the selected bed.</desc>",
            f'  <rect x="0" y="0" width="{bed_width}" height="{bed_depth}" '
            'fill="#f8fafc" stroke="#64748b" stroke-width="1" />',
            f'  <rect x="{margin}" y="{margin}" width="{usable_width}" height="{usable_depth}" '
            'fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 3" />',
            f'  <rect x="{part_x}" y="{part_y}" width="{part_width}" height="{part_depth}" '
            f'fill="{part_fill}" fill-opacity="0.28" stroke="{part_stroke}" stroke-width="2" />',
            "</svg>",
            "",
        )
    )


def _render_run_detail_model_svg(bounds: Bounds3D, bed: BedSize, bed_fit: BedFitResult) -> str:
    width = 960.0
    height = 600.0
    bed_scale = min(760.0 / bed.width_mm, 310.0 / bed.depth_mm)
    bed_w = bed.width_mm * bed_scale
    bed_d = bed.depth_mm * bed_scale
    bed_x = (width - bed_w) / 2.0
    bed_y = 250.0
    part_w = min(bed_w, bounds.width_x * bed_scale)
    part_d = min(bed_d, bounds.depth_y * bed_scale)
    part_x = bed_x + ((bed_w - part_w) / 2.0)
    part_y = bed_y + ((bed_d - part_d) / 2.0)
    part_h = max(24.0, min(140.0, bounds.height_z * bed_scale * 0.8))
    part_fill = "#dbeaf1" if bed_fit.fits else "#f6d5d5"
    part_stroke = "#327d9e" if bed_fit.fits else "#b42323"
    label = (
        f"{_svg_float(bounds.width_x)} x {_svg_float(bounds.depth_y)} x "
        f"{_svg_float(bounds.height_z)} mm"
    )

    return "\n".join(
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {_svg_float(width)} {_svg_float(height)}" '
            'width="960" height="600" role="img" aria-labelledby="title desc">',
            '  <title id="title">Run detail model preview</title>',
            '  <desc id="desc">Deterministic bounds-only model preview with bed footprint.</desc>',
            "  <defs>",
            '    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">',
            '      <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#d4dde5" stroke-width="1"/>',
            "    </pattern>",
            "  </defs>",
            '  <rect width="960" height="600" fill="#f8fafc"/>',
            '  <rect width="960" height="600" fill="url(#grid)" opacity="0.75"/>',
            f'  <polygon points="{_svg_float(bed_x)},{_svg_float(bed_y + bed_d)} '
            f'{_svg_float(bed_x + 95)},{_svg_float(bed_y)} '
            f'{_svg_float(bed_x + bed_w)},{_svg_float(bed_y)} '
            f'{_svg_float(bed_x + bed_w - 95)},{_svg_float(bed_y + bed_d)}" '
            'fill="#ffffff" fill-opacity="0.45" stroke="#7aaabe" stroke-width="2"/>',
            f'  <ellipse cx="{_svg_float(part_x + part_w / 2.0)}" '
            f'cy="{_svg_float(part_y + part_d / 2.0)}" '
            f'rx="{_svg_float(max(18.0, part_w / 2.0))}" '
            f'ry="{_svg_float(max(12.0, part_d / 2.0))}" '
            f'fill="{part_fill}" stroke="{part_stroke}" stroke-width="4" opacity="0.82"/>',
            f'  <ellipse cx="{_svg_float(part_x + part_w * 0.62)}" '
            f'cy="{_svg_float(part_y + part_d * 0.45)}" '
            f'rx="{_svg_float(max(12.0, part_w * 0.18))}" '
            f'ry="{_svg_float(max(8.0, part_d * 0.18))}" '
            'fill="#ffffff" fill-opacity="0.78"/>',
            f'  <path d="M {_svg_float(part_x + part_w * 0.12)} {_svg_float(part_y + part_d * 0.58)} '
            f'C {_svg_float(part_x + part_w * 0.35)} {_svg_float(part_y + part_d * 0.28)}, '
            f'{_svg_float(part_x + part_w * 0.65)} {_svg_float(part_y + part_d * 0.28)}, '
            f'{_svg_float(part_x + part_w * 0.88)} {_svg_float(part_y + part_d * 0.55)}" '
            f'fill="none" stroke="{part_stroke}" stroke-width="{_svg_float(max(5.0, part_h / 18.0))}" '
            'stroke-linecap="round" opacity="0.62"/>',
            f'  <text x="40" y="52" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            'font-size="18" font-weight="700" fill="#17202a">Bounds-only run preview</text>',
            f'  <text x="40" y="84" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="15" fill="#52606d">{label}</text>',
            f'  <text x="40" y="112" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="15" fill="#52606d">bed fit: {"pass" if bed_fit.fits else "fail"}, '
            f'min margin {_svg_float(bed_fit.min_margin_mm)} mm</text>',
            "</svg>",
            "",
        )
    )


def _svg_float(value: float) -> str:
    cleaned = _clean_float(value)
    if float(cleaned).is_integer():
        return str(int(cleaned))
    return f"{cleaned:.6f}".rstrip("0").rstrip(".")


def _clean_float(value: float) -> float:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return 0.0
    nearest_int = round(value)
    if math.isclose(value, nearest_int, abs_tol=1e-12):
        return float(nearest_int)
    return value
