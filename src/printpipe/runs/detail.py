"""UI-ready run detail contract for the local workbench."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from printpipe.beta.physical import build_physical_print_evidence, missing_required_evidence
from printpipe.runs.editing import (
    EditRecipe,
    edit_recipe_to_dict,
    load_edit_recipe,
)


RUN_DETAIL_SCHEMA_VERSION = 1

_PIPELINE_STEPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "input_reference",
        "Input / reference",
        ("input", "classify_input", "extract_references", "select_references"),
    ),
    ("mesh_generation", "Mesh generation", ("mesh_generation", "meshgen", "generated_mesh")),
    ("repair", "Repair", ("repair", "mesh_repair")),
    ("orient_scale", "Orient / scale", ("orient_scale", "geometry", "bed_fit")),
    ("print_profile", "Print profile", ("print_profile", "profile", "profiles")),
    ("bundle", "3MF bundle", ("bundle", "3mf")),
    ("slice_report", "Slice report", ("slice", "slice_report")),
)


def build_run_detail(run_root: str | Path) -> dict[str, Any]:
    """Build the stable data shape the run-detail UI consumes."""

    root = Path(run_root).expanduser().resolve()
    manifest = _read_json(root / "manifest.json")
    report = _read_optional_json(root / "80_reports" / "run_report.json")
    settings = _first_mapping(report.get("settings_changes"))
    metrics = _combined_metrics(report)
    validation = _validation_checks(metrics=metrics, settings=settings)
    warnings = _strings(report.get("warnings"))

    return {
        "schema_version": RUN_DETAIL_SCHEMA_VERSION,
        "run_id": str(manifest.get("run_id") or report.get("run_id") or root.name),
        "run_root": str(root),
        "parent_run": _parent_run_contract(manifest),
        "input": _input_contract(manifest),
        "launch_options": _mapping(manifest.get("launch_options")),
        "settings": settings,
        "printer": {"label": _setting_label(settings, "printer")},
        "material": {"label": _setting_label(settings, "material")},
        "profile": {"label": _setting_label(settings, "profile")},
        "geometry": _geometry_contract(metrics),
        "print_verdict": _print_verdict(validation, warnings),
        "validation": validation,
        "pipeline": _pipeline_contract(report),
        "artifacts": _artifact_groups(report, run_root=root),
        "warnings": warnings,
        "physical_evidence": _physical_evidence_contract(root),
        "edit_recipe": _edit_recipe_contract(root, manifest),
        "rebuild": {
            "available": True,
            "mode": "edit_recipe",
            "creates": "new_run",
        },
    }


def _parent_run_contract(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    parent_run = _mapping(manifest.get("parent_run"))
    return parent_run or None


def _input_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    input_info = _mapping(manifest.get("input"))
    return {
        "kind": str(input_info.get("kind", "unknown")),
        "source_path": _optional_string(input_info.get("source_path")),
        "stored_path": _optional_string(input_info.get("stored_path")),
        "artifact_kind": _optional_string(input_info.get("artifact_kind")),
    }


def _geometry_contract(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "bounds_mm": metrics.get("bounds_mm"),
        "bed_fit": (
            metrics.get("bed_fit")
            or metrics.get("bed_fit_status")
            or _fits_label(metrics.get("fits"))
        ),
        "support_risk": metrics.get("support_risk"),
        "print_time_minutes": metrics.get("print_time_minutes"),
        "filament_g": metrics.get("filament_g") or metrics.get("mass_g"),
    }


def _validation_checks(
    *,
    metrics: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        _manifold_check(metrics),
        _bed_fit_check(metrics),
        _material_profile_check(settings),
        _support_risk_check(metrics),
        _slice_success_check(metrics),
    ]


def _manifold_check(metrics: dict[str, Any]) -> dict[str, str]:
    watertight = metrics.get("watertight")
    non_manifold = metrics.get("non_manifold_edges")
    boundary = metrics.get("boundary_edges")
    if watertight is False or _positive(non_manifold) or _positive(boundary):
        return _check(
            "manifold",
            "Manifold / watertight",
            "fail",
            "Mesh still has open or non-manifold geometry.",
        )
    if watertight is True and _zero_or_missing(non_manifold) and _zero_or_missing(boundary):
        return _check(
            "manifold",
            "Manifold / watertight",
            "pass",
            "Mesh repair reports a closed printable shell.",
        )
    if watertight is None and non_manifold == 0 and boundary == 0:
        return _check(
            "manifold",
            "Manifold / watertight",
            "pass",
            "Mesh topology reports no open or non-manifold edges.",
        )
    return _check(
        "manifold",
        "Manifold / watertight",
        "review",
        "No watertightness metric is available yet.",
    )


def _bed_fit_check(metrics: dict[str, Any]) -> dict[str, str]:
    fits = metrics.get("fits")
    if fits is True:
        margin = metrics.get("min_margin_mm")
        detail = "Oriented footprint fits the selected build plate."
        if isinstance(margin, int | float):
            detail = f"Oriented footprint fits the selected build plate with {margin:g} mm minimum margin."
        return _check("bed_fit", "Bed fit", "pass", detail)
    if fits is False:
        return _check(
            "bed_fit",
            "Bed fit",
            "fail",
            "Oriented footprint does not fit the selected build plate.",
        )

    bed_fit = str(metrics.get("bed_fit") or metrics.get("bed_fit_status") or "").lower()
    if "fit" in bed_fit and "not" not in bed_fit and "fail" not in bed_fit:
        return _check(
            "bed_fit",
            "Bed fit",
            "pass",
            "Oriented footprint fits the selected build plate.",
        )
    if bed_fit:
        return _check("bed_fit", "Bed fit", "fail", f"Bed fit needs attention: {bed_fit}.")
    return _check("bed_fit", "Bed fit", "review", "No bed-fit verdict is available yet.")


def _material_profile_check(settings: dict[str, Any]) -> dict[str, str]:
    labels = [
        _setting_label(settings, "printer"),
        _setting_label(settings, "material"),
        _setting_label(settings, "profile"),
    ]
    present_labels = [label for label in labels if label]
    if present_labels:
        return _check(
            "material_profile",
            "Material / profile",
            "pass",
            " / ".join(present_labels),
        )
    return _check(
        "material_profile",
        "Material / profile",
        "review",
        "Printer/material/profile selection is incomplete.",
    )


def _support_risk_check(metrics: dict[str, Any]) -> dict[str, str]:
    support_risk = str(metrics.get("support_risk") or "").lower()
    if support_risk in {"none", "low"}:
        return _check("support_risk", "Support risk", "pass", "Low support risk.")
    if support_risk in {"high", "fail", "failed"}:
        return _check(
            "support_risk",
            "Support risk",
            "fail",
            "High support risk; revise geometry or support policy.",
        )
    if support_risk:
        return _check(
            "support_risk",
            "Support risk",
            "review",
            f"{support_risk.title()} support risk; inspect support policy.",
        )
    return _check(
        "support_risk",
        "Support risk",
        "review",
        "Support risk has not been classified yet.",
    )


def _slice_success_check(metrics: dict[str, Any]) -> dict[str, str]:
    slice_success = metrics.get("slice_success")
    errors = _strings(metrics.get("errors"))
    return_code = metrics.get("return_code")
    if slice_success is True:
        return _check(
            "slice_success",
            "Slice success",
            "pass",
            "Slice gate completed successfully.",
        )
    if slice_success is False:
        return _check(
            "slice_success",
            "Slice success",
            "fail",
            "Slice gate failed; inspect slicer logs.",
        )
    if errors:
        return _check(
            "slice_success",
            "Slice success",
            "fail",
            f"Slice gate failed: {errors[0]}.",
        )
    if isinstance(return_code, int | float):
        if return_code == 0:
            return _check(
                "slice_success",
                "Slice success",
                "pass",
                "Slice gate completed successfully.",
            )
        return _check(
            "slice_success",
            "Slice success",
            "fail",
            f"Slice gate failed with return code {return_code:g}.",
        )
    return _check(
        "slice_success",
        "Slice success",
        "review",
        "Slice gate has not produced a verdict yet.",
    )


def _print_verdict(checks: list[dict[str, str]], warnings: list[str]) -> dict[str, str]:
    states = {check["state"] for check in checks}
    if "fail" in states:
        return {
            "state": "blocked",
            "label": "Not ready to print",
            "reason": "One or more validation checks failed.",
        }
    if "review" in states or warnings:
        return {
            "state": "review",
            "label": "Review before print",
            "reason": "Warnings remain, but no blocking validation checks failed.",
        }
    return {
        "state": "ready",
        "label": "Ready to print",
        "reason": "All available validation checks passed.",
    }


def _pipeline_contract(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    stages = _as_list(report.get("stages"))
    return [
        _pipeline_step_contract(key=key, label=label, aliases=aliases, stages=stages)
        for key, label, aliases in _PIPELINE_STEPS
    ]


def _pipeline_step_contract(
    *,
    key: str,
    label: str,
    aliases: tuple[str, ...],
    stages: list[Any],
) -> dict[str, Any]:
    stage = _matching_stage(aliases, stages)
    if not stage:
        return {
            "key": key,
            "label": label,
            "status": "unknown",
            "message": "Not run yet.",
            "artifacts": [],
        }
    return {
        "key": key,
        "label": label,
        "status": str(stage.get("status", "unknown")),
        "message": str(stage.get("message", "")),
        "artifacts": _artifact_list(stage.get("artifacts")),
    }


def _artifact_groups(
    report: Mapping[str, Any],
    *,
    run_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for artifact in _artifact_list(report.get("artifacts")):
        kind = artifact["kind"]
        grouped.setdefault(kind, []).append(
            {
                **artifact,
                "present": _artifact_present(artifact.get("path"), run_root=run_root),
            }
        )
    return grouped


def _artifact_list(value: Any) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in _as_list(value):
        if not isinstance(item, Mapping):
            continue
        artifacts.append(
            {
                "kind": str(item.get("kind", "unknown")),
                "label": str(item.get("label", "")),
                "path": _optional_string(item.get("path")),
                "metadata": _mapping(item.get("metadata")),
            }
        )
    return artifacts


def _physical_evidence_contract(root: Path) -> dict[str, Any]:
    json_path = root / "90_physical" / "physical_evidence.json"
    markdown_path = root / "90_physical" / "physical_evidence.md"
    if not json_path.exists():
        return {
            "available": False,
            "missing_required_evidence": ["physical evidence packet"],
            "packet_paths": {},
        }

    payload = _read_optional_json(json_path)
    evidence = build_physical_print_evidence(
        run_id=str(payload.get("run_id", "")),
        material=str(payload.get("material", "")),
        printer=str(payload.get("printer", "")),
        object_label=str(payload.get("object_label", "")),
        print_type=str(payload.get("print_type", "")),
        print_status=str(payload.get("print_status", "")),
        operator=str(payload.get("operator", "")),
        started_at=str(payload.get("started_at", "")),
        completed_at=str(payload.get("completed_at", "")),
        slice_status=str(payload.get("slice_status", "")),
        filament_drying=str(payload.get("filament_drying", "")),
        bed_prep=str(payload.get("bed_prep", "")),
        first_layer=str(payload.get("first_layer", "")),
        adhesion=str(payload.get("adhesion", "")),
        warping=str(payload.get("warping", "")),
        stringing=str(payload.get("stringing", "")),
        layer_bonding=str(payload.get("layer_bonding", "")),
        flex_recovery=str(payload.get("flex_recovery", "")),
        support_removal=str(payload.get("support_removal", "")),
        dimensions_mm=_mapping(payload.get("dimensions_mm")),
        artifacts=_as_list(payload.get("artifacts")),
        notes=_strings(payload.get("notes")),
    )
    packet_paths = {"json": "90_physical/physical_evidence.json"}
    if markdown_path.exists():
        packet_paths["markdown"] = "90_physical/physical_evidence.md"
    return {
        "available": True,
        "schema_version": payload.get("schema_version"),
        "run_id": evidence.run_id,
        "material": evidence.material,
        "printer": evidence.printer,
        "object_label": evidence.object_label,
        "print_type": evidence.print_type,
        "print_status": evidence.print_status,
        "operator": evidence.operator,
        "started_at": evidence.started_at,
        "completed_at": evidence.completed_at,
        "artifacts": [artifact.to_dict() for artifact in evidence.artifacts],
        "missing_required_evidence": missing_required_evidence(evidence),
        "packet_paths": packet_paths,
    }


def _edit_recipe_contract(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    try:
        recipe = load_edit_recipe(root)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        recipe = EditRecipe(parent_run_id=str(manifest.get("run_id", root.name)))
    return edit_recipe_to_dict(recipe)


def _combined_metrics(report: Mapping[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for stage in _as_list(report.get("stages")):
        if isinstance(stage, Mapping):
            stage_metrics = stage.get("metrics")
            if isinstance(stage_metrics, Mapping):
                metrics.update(stage_metrics)
    return metrics


def _matching_stage(aliases: tuple[str, ...], stages: list[Any]) -> Mapping[str, Any] | None:
    normalized_aliases = {_normalize(alias) for alias in aliases}
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        stage_name = _normalize(str(stage.get("stage") or stage.get("name") or ""))
        if stage_name in normalized_aliases or any(
            alias in stage_name
            for alias in normalized_aliases
        ):
            return stage
    return None


def _check(key: str, label: str, state: str, detail: str) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "state": state,
        "detail": detail,
    }


def _setting_label(settings: Mapping[str, Any], prefix: str) -> str:
    for suffix in ("label", "name", "id"):
        value = settings.get(f"{prefix}_{suffix}")
        if value:
            return str(value)
    return ""


def _artifact_present(path_value: Any, *, run_root: Path) -> bool:
    if not isinstance(path_value, str) or not path_value:
        return False
    path = Path(path_value)
    return (path if path.is_absolute() else run_root / path).exists()


def _first_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    for item in _as_list(value):
        if isinstance(item, Mapping):
            return dict(item)
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _positive(value: Any) -> bool:
    return isinstance(value, int | float) and value > 0


def _zero_or_missing(value: Any) -> bool:
    return value is None or value == 0


def _fits_label(value: Any) -> str | None:
    if value is True:
        return "fits"
    if value is False:
        return "fails"
    return None


def _normalize(value: str) -> str:
    return "".join(
        character if character.isalnum() else "_"
        for character in value.lower()
    ).strip("_")


__all__ = ["RUN_DETAIL_SCHEMA_VERSION", "build_run_detail"]
