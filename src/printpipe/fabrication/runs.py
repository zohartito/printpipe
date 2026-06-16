"""Phase-0 bridge: build a FabricationReport from an existing run folder.

Legacy runs predate the fabrication-verification contract, so they carry no
geometry provenance (no dimensions, no per-part face counts). This module is a
*conservative* adapter: it reuses ``build_run_detail`` -- which only reads the
already-written run JSON, it does NOT re-run geometry -- and maps that UI shape
onto a :class:`FabricationReport`. Anything the run detail does not expose
degrades to an empty/None/0 value rather than raising.

Dependency-light by design: stdlib + first-party only. ``build_run_detail``'s
own import chain is pure stdlib + ``printpipe.*`` (no trimesh/numpy), so it is
imported at module level like the rest of the package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printpipe.fabrication.report import (
    Check,
    ExportResult,
    FabricationReport,
    PartResult,
    Status,
    Target,
)
from printpipe.runs.detail import build_run_detail

# Validation checks that map to printability Checks (everything except manifold,
# which drives the single PartResult's validity instead).
_PRINTABILITY_KEYS = ("bed_fit", "material_profile", "support_risk", "slice_success")

# run-detail validation state -> fabrication Status.
_STATE_TO_STATUS = {
    "pass": Status.PASS,
    "review": Status.FLAG,
    "fail": Status.FAIL,
}

_DEFAULT_TOLERANCE_MM = 0.01


def build_fabrication_report(run_root: str | Path) -> FabricationReport:
    """Adapt an existing run folder into a :class:`FabricationReport`.

    This is a Phase-0 bridge: it does not re-run geometry. It reads the run's
    already-written JSON via :func:`build_run_detail` and maps the result onto
    the fabrication-verification contract. Missing keys degrade gracefully
    (empty list / ``None`` / ``0``); a malformed run never raises ``KeyError``.
    """
    detail = build_run_detail(run_root)

    checks_by_key = _checks_by_key(detail.get("validation"))
    part = _build_part(detail, manifold=checks_by_key.get("manifold"))
    printability = _build_printability(checks_by_key)

    return FabricationReport(
        units="mm",
        tolerance_mm=_DEFAULT_TOLERANCE_MM,
        wall_thickness_mm=0.0,  # unknown for legacy runs
        target=Target.PRINT,
        dimensions=[],  # legacy runs carry no provenance dimensions yet
        parts=[part],
        valid_solids=f"{1 if part.valid else 0} / 1",
        printability=printability,
        orientation=None,
        packing=None,
        exports=_build_exports(detail),
        agent_summary=_build_agent_summary(detail),
    )


def _checks_by_key(validation: Any) -> dict[str, dict[str, Any]]:
    """Index the run-detail validation list by its ``key`` field, null-safe."""
    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(validation, list):
        return indexed
    for check in validation:
        if isinstance(check, dict):
            key = check.get("key")
            if isinstance(key, str):
                indexed[key] = check
    return indexed


def _build_part(detail: dict[str, Any], *, manifold: dict[str, Any] | None) -> PartResult:
    """Build the single PartResult; validity derives from the manifold check."""
    part_id = _part_id(detail)
    valid = bool(manifold) and manifold.get("state") == "pass"
    failure_reason = None
    if not valid:
        # Prefer the manifold check's own detail; fall back to a generic note.
        if manifold and manifold.get("detail"):
            failure_reason = str(manifold["detail"])
        else:
            failure_reason = "Manifold / watertight check did not pass."
    return PartResult(
        id=part_id,
        source_faces=0,  # legacy runs expose no triangle count
        thicken_dir_mm=None,
        solid=valid,
        valid=valid,
        failure_reason=failure_reason,
    )


def _part_id(detail: dict[str, Any]) -> str:
    """Derive a part id from the run id/name, defaulting to 'model'."""
    run_id = detail.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    return "model"


def _build_printability(checks_by_key: dict[str, dict[str, Any]]) -> list[Check]:
    """Map non-manifold validation checks into printability Checks."""
    checks: list[Check] = []
    for key in _PRINTABILITY_KEYS:
        check = checks_by_key.get(key)
        if check is None:
            continue
        status = _STATE_TO_STATUS.get(str(check.get("state", "")), Status.FLAG)
        detail = str(check.get("detail", ""))
        checks.append(Check(name=key, status=status, detail=detail))
    return checks


def _build_exports(detail: dict[str, Any]) -> ExportResult:
    """Stub exports; set openable_3mf if the run exposes an openable .3mf artifact."""
    openable = _openable_3mf(detail.get("artifacts"))
    if openable is None:
        return ExportResult()
    return ExportResult(openable_3mf=openable)


def _openable_3mf(artifacts: Any) -> str | None:
    """Find an openable project .3mf path, excluding sliced ``*.gcode.3mf``.

    ``build_run_detail`` groups artifacts as ``{kind: [{path, present, ...}]}``.
    """
    if not isinstance(artifacts, dict):
        return None
    for entries in artifacts.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                continue
            if path.endswith(".gcode.3mf") or not path.endswith(".3mf"):
                continue
            if entry.get("present") is False:
                continue
            return path
    return None


def _build_agent_summary(detail: dict[str, Any]) -> str:
    """Combine the print verdict reason with any warnings into a short string."""
    parts: list[str] = []
    verdict = detail.get("print_verdict")
    if isinstance(verdict, dict):
        reason = verdict.get("reason")
        if isinstance(reason, str) and reason:
            parts.append(reason)
    warnings = detail.get("warnings")
    if isinstance(warnings, list):
        warning_strings = [str(w) for w in warnings if w]
        if warning_strings:
            parts.append("Warnings: " + "; ".join(warning_strings))
    return " ".join(parts)


__all__ = ["build_fabrication_report"]
