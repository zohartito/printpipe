"""JSON serialization for the fabrication-verification report.

Mirrors the ``to_dict()`` style in ``printpipe.mesh.validate``: enums emit their
``.value``, optional fields collapse to ``None``, and the output is strictly
JSON-serializable (str/int/float/bool/None/list/dict only). No geometry objects,
no trimesh/numpy.
"""

from __future__ import annotations

from typing import Any

from printpipe.fabrication.report import (
    Check,
    Dimension,
    ExportResult,
    FabricationReport,
    OrientationCandidate,
    PackingResult,
    PartResult,
)

FABRICATION_REPORT_SCHEMA_VERSION = 1


def to_dict(report: FabricationReport) -> dict[str, Any]:
    """Serialize a fabrication report to a JSON-ready dict."""
    return {
        "schema_version": FABRICATION_REPORT_SCHEMA_VERSION,
        "units": report.units,
        "tolerance_mm": report.tolerance_mm,
        "wall_thickness_mm": report.wall_thickness_mm,
        "target": report.target.value,
        "dimensions": [_dimension_to_dict(dimension) for dimension in report.dimensions],
        "parts": [_part_to_dict(part) for part in report.parts],
        "valid_solids": report.valid_solids,
        "printability": [_check_to_dict(check) for check in report.printability],
        "orientation": (
            _orientation_to_dict(report.orientation)
            if report.orientation is not None
            else None
        ),
        "packing": (
            _packing_to_dict(report.packing) if report.packing is not None else None
        ),
        "exports": _exports_to_dict(report.exports),
        "agent_summary": report.agent_summary,
        "ready_to_print": report.ready_to_print,
    }


def _dimension_to_dict(dimension: Dimension) -> dict[str, Any]:
    return {
        "name": dimension.name,
        "value_mm": dimension.value_mm,
        "provenance": dimension.provenance.value,
        "fit_critical": dimension.fit_critical,
        "confidence": dimension.confidence,
        "source": dimension.source,
    }


def _part_to_dict(part: PartResult) -> dict[str, Any]:
    return {
        "id": part.id,
        "source_faces": part.source_faces,
        "thicken_dir_mm": part.thicken_dir_mm,
        "solid": part.solid,
        "valid": part.valid,
        "failure_reason": part.failure_reason,
    }


def _check_to_dict(check: Check) -> dict[str, Any]:
    return {
        "name": check.name,
        "status": check.status.value,
        "detail": check.detail,
        "depends_on_assumed_dim": check.depends_on_assumed_dim,
    }


def _orientation_to_dict(orientation: OrientationCandidate) -> dict[str, Any]:
    return {
        "name": orientation.name,
        "support_volume_mm3": orientation.support_volume_mm3,
        "stability": orientation.stability,
        "score": orientation.score,
    }


def _packing_to_dict(packing: PackingResult) -> dict[str, Any]:
    return {
        "unit": packing.unit,
        "units_used": packing.units_used,
        "layout": [dict(item) for item in packing.layout],
        "efficiency": packing.efficiency,
        "unplaced": list(packing.unplaced),
    }


def _exports_to_dict(exports: ExportResult) -> dict[str, Any]:
    return {
        "stl_paths": list(exports.stl_paths),
        "openable_3mf": exports.openable_3mf,
        "dxf_layers": list(exports.dxf_layers),
        "scale": exports.scale,
    }
