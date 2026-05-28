"""End-to-end PrintPipe pipeline orchestrators."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from printpipe.bambu.profiles import load_profile, resolve_inherits
from printpipe.bambu.profiles.sources import default_bambu_orca_profile_roots
from printpipe.bambu.slicer import run_bambu_cli_slice_stage
from printpipe.bambu.threemf import BambuProfileIds, GuiSafeTransform, validate_bundle
from printpipe.bambu.threemf.mesh_adapter import write_bundle_from_ascii_stl
from printpipe.calibration import write_flex_coupon_artifacts
from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageReceipt, StageStatus
from printpipe.geometry import (
    BedSize,
    candidate_rotations,
    read_ascii_stl_vertices,
    select_top_orientations,
    write_bed_fit_preview_artifacts,
    write_oriented_ascii_stl_artifacts,
    write_run_detail_model_preview_artifacts,
    write_scaled_ascii_stl_artifacts,
)
from printpipe.inputs import prepare_input
from printpipe.materials.abs_asa import MaterialRule as AbsAsaMaterialRule
from printpipe.materials.abs_asa import get_abs_asa_rule
from printpipe.materials.petg import build_petg_overrides
from printpipe.materials.pc_pa import MaterialRule as PcPaMaterialRule
from printpipe.materials.pc_pa import get_material_rule as get_pc_pa_material_rule
from printpipe.materials.pla import build_pla_overrides
from printpipe.materials.tpu import TpuMaterialRule, get_tpu_rule
from printpipe.mesh.repair import repair_mesh_file_to_receipt
from printpipe.meshgen import (
    ExistingMeshProvider,
    Hunyuan3DProvider,
    MeshGenProvider,
    MeshGenRequest,
    MeshGenResult,
    generate_with_retries,
)
from printpipe.preflight import build_pre_print_checklist
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs import (
    RunLayout,
    create_prompt_run,
    create_run,
    edit_recipe_to_dict,
    load_edit_recipe,
    load_run,
)


NON_MESH_MESHGEN_MESSAGE = (
    "media meshgen requires a configured provider; set PRINTPIPE_HUNYUAN3D_COMMAND "
    "for the local Hunyuan3D adapter"
)
DEFAULT_BED = BedSize(width_mm=256.0, depth_mm=256.0)
DEFAULT_PROFILE_IDS = BambuProfileIds(
    filament_settings_id="Generic PLA",
    print_settings_id="0.20mm Standard",
    printer_settings_id="Bambu Lab P2S 0.4 nozzle",
    printer_model="Bambu Lab P2S",
    printer_variant="0.4",
    nozzle_diameter="0.4",
    printable_height="256",
)
DEFAULT_BBL_P2S_PROCESS_PROFILE = "0.20mm Standard @BBL P2S"
BAMBU_TPU_90A_FILAMENT_PROFILE = "Bambu TPU 90A @BBL P2S"
GENERIC_PLA_FILAMENT_PROFILE_FALLBACKS = (
    "Generic PLA @BBL P2S",
    "Bambu PLA Basic @BBL P2S",
    "Bambu PLA Basic @base",
)
GENERIC_PLA_PLUS_FILAMENT_PROFILE_FALLBACKS = (
    "Generic PLA+ @BBL P2S",
    "Bambu PLA Tough @BBL P2S",
    *GENERIC_PLA_FILAMENT_PROFILE_FALLBACKS,
)
GENERIC_PETG_FILAMENT_PROFILE_FALLBACKS = (
    "Generic PETG @BBL P2S",
    "Bambu PETG Basic @BBL P2S",
    "Generic PETG @base",
    "Bambu PETG Basic @base",
)


@dataclass(frozen=True)
class PipelineResult:
    layout: RunLayout
    stages: tuple[StageReceipt, ...]
    artifacts: tuple[Artifact, ...]


class PipelineError(RuntimeError):
    def __init__(self, message: str, result: PipelineResult) -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class BundleProfileConfig:
    profile_ids: BambuProfileIds
    filament_settings: Mapping[str, Any]
    process_settings: Mapping[str, Any]
    printer_settings: Mapping[str, Any]
    material_rule_slug: str | None = None
    material_rule_name: str | None = None


def run_existing_mesh_pipeline(
    input_path: Path,
    runs_dir: Path = Path("runs"),
    *,
    material: str = "Generic PLA",
    printer: str = DEFAULT_PROFILE_IDS.printer_model,
    use_case: str = "print",
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    run_slice: bool = False,
    slice_executable: str | Path | None = None,
    meshgen_provider: MeshGenProvider | None = None,
    prompt_hint: str | None = None,
) -> PipelineResult:
    """Run the currently wired pipeline spine for mesh or media input."""

    layout = create_run(input_path, runs_dir)
    return run_existing_mesh_pipeline_on_layout(
        layout,
        material=material,
        printer=printer,
        use_case=use_case,
        settings_changes=settings_changes,
        run_slice=run_slice,
        slice_executable=slice_executable,
        meshgen_provider=meshgen_provider,
        prompt_hint=prompt_hint,
    )


def run_prompt_pipeline(
    prompt: str,
    runs_dir: Path = Path("runs"),
    *,
    material: str = "Generic PLA",
    printer: str = DEFAULT_PROFILE_IDS.printer_model,
    use_case: str = "print",
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    meshgen_provider: MeshGenProvider | None = None,
) -> PipelineResult:
    """Run prompt-only input through configured reference generation and meshgen."""

    layout = create_prompt_run(prompt, runs_dir)
    return run_existing_mesh_pipeline_on_layout(
        layout,
        material=material,
        printer=printer,
        use_case=use_case,
        settings_changes=settings_changes,
        meshgen_provider=meshgen_provider,
        prompt_hint=prompt,
    )


def run_existing_mesh_pipeline_on_layout(
    layout: RunLayout,
    *,
    source_mesh_path: Path | None = None,
    initial_stages: Sequence[StageReceipt] = (),
    initial_warnings: Sequence[str] = (),
    material: str = "Generic PLA",
    printer: str = DEFAULT_PROFILE_IDS.printer_model,
    use_case: str = "print",
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    run_slice: bool = False,
    slice_executable: str | Path | None = None,
    meshgen_provider: MeshGenProvider | None = None,
    prompt_hint: str | None = None,
) -> PipelineResult:
    """Run the mesh pipeline inside a pre-created run layout."""

    source_mesh = Path(source_mesh_path) if source_mesh_path is not None else layout.original_input
    selected_reference_artifacts: tuple[Artifact, ...] = ()
    if source_mesh_path is None:
        input_result = prepare_input(layout.original_input, layout.frames_dir)
        stages = [*initial_stages, *input_result.receipts]
        input_kind = input_result.kind
        source_artifact = input_result.mesh_artifact
        selected_reference_artifacts = input_result.selected_references
    else:
        stages = list(initial_stages)
        input_kind = InputKind.MESH
        source_artifact = Artifact(
            kind=ArtifactKind.ORIGINAL_INPUT,
            path=source_mesh,
            label="Pipeline source mesh",
            metadata={"source": "layout_override"},
        )

    if input_kind == InputKind.MESH and source_artifact is None:
        message = "existing mesh input did not produce a mesh artifact"
        stages.append(
            StageReceipt(
                stage="meshgen",
                status=StageStatus.FAILED,
                message=message,
                metrics={"input_kind": input_kind.value},
            )
        )
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(message,),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(message, result)

    provider: MeshGenProvider
    if input_kind == InputKind.MESH:
        provider = ExistingMeshProvider()
        request = MeshGenRequest(
            input_kind=InputKind.MESH,
            source_paths=(Path(source_artifact.path),),
            output_formats=(_mesh_output_format(Path(source_artifact.path)),),
            max_attempts=1,
        )
    else:
        reference_paths = tuple(Path(artifact.path) for artifact in selected_reference_artifacts)
        if not reference_paths:
            message = f"{input_kind.value} input did not produce selected references for meshgen"
            upstream_failures = [
                receipt.message
                for receipt in stages
                if receipt.status == StageStatus.FAILED and receipt.stage != "meshgen"
            ]
            failure_message = upstream_failures[-1] if upstream_failures else message
            stages.append(
                StageReceipt(
                    stage="meshgen",
                    status=StageStatus.FAILED,
                    message=failure_message,
                    metrics={"input_kind": input_kind.value},
                )
            )
            result = _write_pipeline_reports(
                layout,
                stages=tuple(stages),
                warnings=(failure_message,),
                material=material,
                printer=printer,
                use_case=use_case,
                settings_changes=settings_changes,
            )
            raise PipelineError(failure_message, result)

        provider = meshgen_provider or Hunyuan3DProvider()
        provider_input_kind = InputKind.IMAGE if input_kind == InputKind.PROMPT else input_kind
        request = MeshGenRequest(
            input_kind=provider_input_kind,
            source_paths=reference_paths,
            reference_images=reference_paths,
            output_formats=("stl", "glb", "obj"),
            prompt_hint=prompt_hint,
            provider_params={"original_input": str(layout.original_input)},
        )

    mesh_result = generate_with_retries(provider, request, layout)
    stages.append(_meshgen_stage_receipt(mesh_result))

    warnings = (*initial_warnings, *_warnings_for_mesh_result(mesh_result))
    if mesh_result.status != StageStatus.SUCCEEDED:
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=warnings,
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        message = (
            mesh_result.error.message
            if mesh_result.error is not None
            else "existing mesh import failed"
        )
        raise PipelineError(message, result)

    imported_mesh = mesh_result.artifact.path if mesh_result.artifact is not None else None
    if imported_mesh is None:
        message = "existing mesh import did not produce an artifact"
        stages.append(
            StageReceipt(
                stage="meshgen_artifact_gate",
                status=StageStatus.FAILED,
                message=message,
            )
        )
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(message,),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(message, result)

    repair_receipt = repair_mesh_file_to_receipt(
        imported_mesh,
        layout.repair_dir / f"{imported_mesh.stem}_repaired.stl",
        stats_path=layout.repair_dir / f"{imported_mesh.stem}_repair.json",
        allow_non_watertight=True,
    )
    stages.append(repair_receipt)
    warnings = (*warnings, *_warnings_for_receipts((repair_receipt,)))
    if repair_receipt.status == StageStatus.FAILED:
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=warnings,
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(repair_receipt.message, result)

    orientation_source = _orientation_source_for_ascii_pipeline(repair_receipt, imported_mesh)
    fallback_warning = _orientation_source_warning(
        repair_receipt,
        imported_mesh,
        orientation_source,
    )
    if fallback_warning is not None:
        warnings = (*warnings, fallback_warning)
    orientation_receipt = write_oriented_ascii_stl_artifacts(
        orientation_source,
        layout.geometry_dir,
        stem=f"{imported_mesh.stem}_oriented",
    )
    stages.append(orientation_receipt)
    if orientation_receipt.status != StageStatus.SUCCEEDED:
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(*warnings, orientation_receipt.message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(orientation_receipt.message, result)

    oriented_mesh = _first_artifact_path(orientation_receipt, "oriented_mesh")
    if oriented_mesh is None:
        message = "orientation stage did not produce an oriented mesh artifact"
        stages.append(
            StageReceipt(
                stage="orientation_artifact_gate",
                status=StageStatus.FAILED,
                message=message,
            )
        )
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(*warnings, message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(message, result)

    vertices = read_ascii_stl_vertices(oriented_mesh)
    candidates = candidate_rotations(vertices, DEFAULT_BED)
    selected = select_top_orientations(candidates, require_bed_fit=True)
    bed_preview_receipt = write_bed_fit_preview_artifacts(
        selected[0] if selected else candidates[0],
        DEFAULT_BED,
        layout.reports_dir,
        stem="bed_fit",
    )
    stages.append(bed_preview_receipt)
    model_preview_receipt = write_run_detail_model_preview_artifacts(
        selected[0] if selected else candidates[0],
        DEFAULT_BED,
        layout.geometry_dir,
        stem="run_detail_model_preview",
    )
    stages.append(model_preview_receipt)

    object_name = _bundle_object_name(mesh_result.provider_id, imported_mesh)
    bundle_path = layout.bundle_dir / f"{object_name}.3mf"
    bundle_profile = _bundle_profile_config(material)
    write_bundle_from_ascii_stl(
        oriented_mesh,
        bundle_path,
        bundle_profile.profile_ids,
        object_name=object_name,
        transform=GuiSafeTransform.bed_center(DEFAULT_BED.width_mm, DEFAULT_BED.depth_mm),
        filament_settings=bundle_profile.filament_settings,
        process_settings=bundle_profile.process_settings,
        printer_settings=bundle_profile.printer_settings,
    )
    stages.append(
        _bundle_stage_receipt(
            bundle_path,
            oriented_mesh,
            object_name,
            profile_ids=bundle_profile.profile_ids,
            material_rule_slug=bundle_profile.material_rule_slug,
            material_rule_name=bundle_profile.material_rule_name,
        )
    )

    validation_receipt = _bundle_validation_receipt(
        bundle_path,
        layout.bundle_dir / f"{object_name}_bundle_validation.json",
    )
    stages.append(validation_receipt)
    if validation_receipt.status != StageStatus.SUCCEEDED:
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(*warnings, validation_receipt.message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(validation_receipt.message, result)

    slice_receipt = (
        run_bambu_cli_slice_stage(
            three_mf_path=bundle_path,
            run_layout=layout,
            executable=slice_executable,
        )
        if run_slice
        else _slice_not_requested_receipt()
    )
    stages.append(slice_receipt)
    if run_slice and slice_receipt.status != StageStatus.SUCCEEDED:
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(*warnings, slice_receipt.message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(slice_receipt.message, result)

    return _write_pipeline_reports(
        layout,
        stages=tuple(stages),
        warnings=warnings,
        material=material,
        printer=printer,
        use_case=use_case,
        settings_changes=settings_changes,
    )


def run_edit_recipe_pipeline(
    edit_run_root: str | Path,
    *,
    material: str = "Generic PLA",
    printer: str = DEFAULT_PROFILE_IDS.printer_model,
    use_case: str = "print",
    run_slice: bool = False,
    slice_executable: str | Path | None = None,
) -> PipelineResult:
    """Rebuild an edit run from its saved edit_recipe.json."""

    layout = load_run(edit_run_root)
    recipe = load_edit_recipe(layout.root)
    recipe_payload = edit_recipe_to_dict(recipe)
    settings_changes: tuple[Mapping[str, Any], ...] = (
        {"edit_recipe": recipe_payload, "source": "edit_recipe_rebuild"},
    )

    try:
        source_mesh = _resolve_edit_source_mesh(layout)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        failure = StageReceipt(
            stage="edit_recipe.source_mesh",
            status=StageStatus.FAILED,
            message=str(exc),
            metrics={"parent_run_id": recipe.parent_run_id},
        )
        result = _write_pipeline_reports(
            layout,
            stages=(failure,),
            warnings=(str(exc),),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(str(exc), result) from exc

    source_receipt = StageReceipt(
        stage="edit_recipe.source_mesh",
        status=StageStatus.SUCCEEDED,
        message="selected source mesh for edit recipe rebuild",
        artifacts=(
            Artifact(
                kind=ArtifactKind.ORIGINAL_INPUT,
                path=source_mesh,
                label="Edit rebuild source mesh",
                metadata={"parent_run_id": recipe.parent_run_id},
            ),
        ),
        metrics={"source_mesh": source_mesh},
    )
    edit_receipt = write_scaled_ascii_stl_artifacts(
        source_mesh,
        layout.input_dir,
        overall_scale=recipe.scale.overall,
        axis_scale=(recipe.scale.x, recipe.scale.y, recipe.scale.z),
        stem=f"{source_mesh.stem}_edit_recipe_source",
        metadata=recipe_payload,
    )
    initial_stages = (source_receipt, edit_receipt)
    semantic_warnings = _edit_recipe_warnings(recipe_payload)
    if edit_receipt.status != StageStatus.SUCCEEDED:
        result = _write_pipeline_reports(
            layout,
            stages=initial_stages,
            warnings=(*semantic_warnings, edit_receipt.message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(edit_receipt.message, result)

    edited_source = _first_artifact_path(edit_receipt, "original_input")
    if edited_source is None:
        message = "edit recipe did not produce a rebuild source mesh"
        result = _write_pipeline_reports(
            layout,
            stages=initial_stages,
            warnings=(*semantic_warnings, message),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(message, result)

    return run_existing_mesh_pipeline_on_layout(
        layout,
        source_mesh_path=edited_source,
        initial_stages=initial_stages,
        initial_warnings=semantic_warnings,
        material=material,
        printer=printer,
        use_case=use_case,
        settings_changes=settings_changes,
        run_slice=run_slice,
        slice_executable=slice_executable,
    )


def _resolve_edit_source_mesh(layout: RunLayout) -> Path:
    if _is_ascii_stl_path(layout.original_input):
        return layout.original_input

    manifest = _read_json_mapping(layout.manifest_path)
    parent_run = manifest.get("parent_run")
    if not isinstance(parent_run, Mapping):
        raise ValueError("edit run manifest does not record a parent run")
    parent_root_value = parent_run.get("run_root")
    if not isinstance(parent_root_value, str) or not parent_root_value:
        raise ValueError("edit run manifest does not record a parent run root")

    parent_root = Path(parent_root_value).expanduser().resolve()
    parent_report = _read_json_mapping(parent_root / "80_reports" / "run_report.json")
    artifacts = parent_report.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("parent run report does not contain artifacts")

    for preferred_kind in ("oriented_mesh", "repaired_mesh", "generated_mesh"):
        for artifact in artifacts:
            if not isinstance(artifact, Mapping) or artifact.get("kind") != preferred_kind:
                continue
            path_value = artifact.get("path")
            if not isinstance(path_value, str) or not path_value:
                continue
            candidate = Path(path_value)
            if not candidate.is_absolute():
                candidate = parent_root / candidate
            if _is_ascii_stl_path(candidate):
                return candidate

    raise ValueError("parent run has no ASCII STL mesh artifact to rebuild from")


def _is_ascii_stl_path(path: Path) -> bool:
    return path.exists() and path.suffix.lower() == ".stl" and _can_read_ascii_stl(path)


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _edit_recipe_warnings(recipe_payload: Mapping[str, Any]) -> tuple[str, ...]:
    intent = recipe_payload.get("geometry_intent")
    targets = recipe_payload.get("targets_mm")
    warnings: list[str] = []

    if isinstance(intent, Mapping):
        semantic_fields = (
            "upper_width_delta_mm",
            "opening_width_delta_mm",
            "arch_height_delta_mm",
            "wall_thickness_mm",
        )
        has_semantic_intent = any(
            _nonzero_or_present(intent.get(field_name))
            for field_name in semantic_fields
        )
        if has_semantic_intent:
            warnings.append(
                "edit_recipe: deterministic rebuild applied scale fields only; "
                "upper/opening/arch/wall-thickness intent is recorded for review "
                "but not semantically sculpted yet"
            )

    if isinstance(targets, Mapping) and any(
        _nonzero_or_present(targets.get(field_name))
        for field_name in ("length", "width", "height")
    ):
        warnings.append(
            "edit_recipe: target dimensions are recorded for review but are not "
            "used to resize geometry yet; set scale fields for deterministic resizing"
        )

    support_strategy = str(recipe_payload.get("support_strategy") or "auto")
    if support_strategy != "auto":
        warnings.append(
            "edit_recipe: support strategy is recorded for bundling/review but "
            "does not change geometry in deterministic rebuilds yet"
        )

    instruction = str(recipe_payload.get("instruction") or "").strip()
    if instruction:
        warnings.append(
            "edit_recipe: freeform instruction is recorded for review but is "
            "not semantically interpreted by deterministic rebuilds yet"
        )

    return tuple(warnings)


def _nonzero_or_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, int | float):
        return value != 0
    return True


def _meshgen_stage_receipt(result: MeshGenResult) -> StageReceipt:
    artifacts = (result.artifact,) if result.artifact is not None else ()
    if result.provider_id == "existing_mesh":
        message = "imported existing mesh with ExistingMeshProvider"
    else:
        message = f"generated mesh with {result.provider_id}"
    if result.status != StageStatus.SUCCEEDED and result.error is not None:
        message = result.error.message

    return StageReceipt(
        stage="meshgen",
        status=result.status,
        message=message,
        artifacts=artifacts,
        metrics={
            "provider_id": result.provider_id,
            "attempt_count": result.attempt_count,
            "wall_seconds": result.timing.wall_seconds,
        },
    )


def _write_pipeline_reports(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    warnings: Sequence[str] = (),
    material: str = "Generic PLA",
    printer: str = DEFAULT_PROFILE_IDS.printer_model,
    use_case: str = "print",
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
) -> PipelineResult:
    report_stages = _stages_with_validation_artifacts(
        layout,
        stages=stages,
        material=material,
        use_case=use_case,
    )
    pre_print_checklist = build_pre_print_checklist(
        material=material,
        printer=printer,
        use_case=use_case,
        slice_gate_status=_slice_gate_status(report_stages),
    )
    pre_print_checklist = _attach_validation_artifacts_to_checklist(
        layout,
        checklist=pre_print_checklist,
        stages=report_stages,
    )
    report_dict = build_run_report_dict(
        layout,
        stages=report_stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    report_json, report_markdown = write_run_report(
        layout,
        stages=report_stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    report_html = write_html_report(layout, report_dict)
    return PipelineResult(
        layout=layout,
        stages=tuple(report_stages),
        artifacts=(*_stage_artifacts(report_stages), report_json, report_markdown, report_html),
    )


def _stages_with_validation_artifacts(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    material: str,
    use_case: str,
) -> tuple[StageReceipt, ...]:
    if not _is_flexible_material(material):
        return tuple(stages)
    if any(receipt.stage == "validation.flex_coupon" for receipt in stages):
        return tuple(stages)
    return (
        *stages,
        write_flex_coupon_artifacts(
            layout.geometry_dir,
            material=material,
            use_case=use_case,
        ),
    )


def _attach_validation_artifacts_to_checklist(
    layout: RunLayout,
    *,
    checklist: Sequence[Mapping[str, Any]],
    stages: Sequence[StageReceipt],
) -> list[dict[str, Any]]:
    coupon_artifact = _flex_coupon_artifact_path(layout, stages)
    if coupon_artifact is None:
        return [dict(item) for item in checklist]

    enriched: list[dict[str, Any]] = []
    for item in checklist:
        payload = dict(item)
        if payload.get("id") == "flex_coupon_first":
            metadata = dict(_mapping(payload.get("metadata")))
            metadata["coupon_artifact"] = coupon_artifact
            payload["metadata"] = metadata
        enriched.append(payload)
    return enriched


def _flex_coupon_artifact_path(layout: RunLayout, stages: Sequence[StageReceipt]) -> str | None:
    for receipt in stages:
        if receipt.stage != "validation.flex_coupon" or receipt.status != StageStatus.SUCCEEDED:
            continue
        for artifact in receipt.artifacts:
            if artifact.kind == ArtifactKind.CALIBRATION_MESH:
                return artifact.path.relative_to(layout.root).as_posix()
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _is_flexible_material(material: str) -> bool:
    normalized = material.upper()
    return "TPU" in normalized or "TPE" in normalized or "FLEX" in normalized


def _stage_artifacts(stages: Sequence[StageReceipt]) -> tuple[Artifact, ...]:
    return tuple(artifact for stage in stages for artifact in stage.artifacts)


def _warnings_for_mesh_result(result: MeshGenResult) -> tuple[str, ...]:
    if result.status == StageStatus.SUCCEEDED:
        return ()
    if result.error is None:
        if result.provider_id == "existing_mesh":
            return ("existing mesh import failed",)
        return (f"mesh generation failed with {result.provider_id}",)
    return (result.error.message,)


def _warnings_for_receipts(receipts: Sequence[StageReceipt]) -> tuple[str, ...]:
    return tuple(
        f"{receipt.stage}: {receipt.message}"
        for receipt in receipts
        if receipt.status not in {StageStatus.SUCCEEDED}
    )


def _orientation_source_for_ascii_pipeline(repair_receipt: StageReceipt, imported_mesh: Path) -> Path:
    repaired_mesh = _first_artifact_path(repair_receipt, "repaired_mesh")
    if repaired_mesh is not None and _can_read_ascii_stl(repaired_mesh):
        return repaired_mesh
    return imported_mesh


def _orientation_source_warning(
    repair_receipt: StageReceipt,
    imported_mesh: Path,
    orientation_source: Path,
) -> str | None:
    if orientation_source != imported_mesh:
        return None
    repaired_mesh = _first_artifact_path(repair_receipt, "repaired_mesh")
    if repaired_mesh is None:
        return None
    return (
        "mesh_repair: repaired mesh is not ASCII STL-readable by the current "
        "orientation/bundle adapters; using imported mesh for downstream artifacts"
    )


def _first_artifact_path(receipt: StageReceipt, kind_value: str) -> Path | None:
    for artifact in receipt.artifacts:
        if artifact.kind.value == kind_value:
            return artifact.path
    return None


def _can_read_ascii_stl(path: Path) -> bool:
    try:
        read_ascii_stl_vertices(path)
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return True


def _bundle_stage_receipt(
    bundle_path: Path,
    source_mesh: Path,
    object_name: str,
    *,
    profile_ids: BambuProfileIds,
    material_rule_slug: str | None = None,
    material_rule_name: str | None = None,
) -> StageReceipt:
    metadata: dict[str, Any] = {
        "source_mesh": source_mesh,
        "object_name": object_name,
        "profile_ids": profile_ids,
    }
    if material_rule_slug:
        metadata["material_rule_slug"] = material_rule_slug
    if material_rule_name:
        metadata["material_rule_name"] = material_rule_name

    return StageReceipt(
        stage="bundle",
        status=StageStatus.SUCCEEDED,
        message="wrote Bambu 3MF bundle from oriented ASCII STL",
        artifacts=(
            Artifact(
                kind=ArtifactKind.THREEMF,
                path=bundle_path,
                label="Bambu 3MF bundle",
                metadata=metadata,
            ),
        ),
        metrics={
            "source_mesh": source_mesh,
            "bundle_path": bundle_path,
            "object_name": object_name,
            "filament_settings_id": profile_ids.filament_settings_id,
            "print_settings_id": profile_ids.print_settings_id,
        },
    )


def _bundle_profile_config(material: str) -> BundleProfileConfig:
    profiles = _available_bambu_profiles()
    printer_settings = _resolved_bambu_profile_settings(
        DEFAULT_PROFILE_IDS.printer_settings_id,
        profiles=profiles,
    )
    tpu_rule = _tpu_rule_for_material(material)
    if tpu_rule is not None:
        profile_ids = BambuProfileIds(
            filament_settings_id=_tpu_filament_settings_id(tpu_rule),
            print_settings_id=_tpu_print_settings_id(tpu_rule),
            printer_settings_id=DEFAULT_PROFILE_IDS.printer_settings_id,
            printer_model=DEFAULT_PROFILE_IDS.printer_model,
            printer_variant=DEFAULT_PROFILE_IDS.printer_variant,
            nozzle_diameter=DEFAULT_PROFILE_IDS.nozzle_diameter,
            printable_height=DEFAULT_PROFILE_IDS.printable_height,
        )
        base_filament_settings = _resolved_bambu_profile_settings(
            profile_ids.filament_settings_id,
            BAMBU_TPU_90A_FILAMENT_PROFILE,
            profiles=profiles,
        )
        base_process_settings = _resolved_bambu_profile_settings(
            profile_ids.print_settings_id,
            DEFAULT_BBL_P2S_PROCESS_PROFILE,
            DEFAULT_PROFILE_IDS.print_settings_id,
            profiles=profiles,
        )
        return BundleProfileConfig(
            profile_ids=profile_ids,
            filament_settings={**base_filament_settings, **tpu_rule.filament_overrides},
            process_settings={**base_process_settings, **tpu_rule.process_overrides},
            printer_settings=printer_settings,
            material_rule_slug=tpu_rule.slug,
            material_rule_name=tpu_rule.name,
        )

    petg_overrides = _petg_overrides_for_material(material)
    if petg_overrides is not None:
        return _generic_material_bundle_profile_config(
            profile_ids=_profile_ids_with_filament("Generic PETG"),
            filament_profile_fallbacks=GENERIC_PETG_FILAMENT_PROFILE_FALLBACKS,
            material_overrides=petg_overrides,
            printer_settings=printer_settings,
            profiles=profiles,
            material_rule_slug=str(petg_overrides["material_id"]),
            material_rule_name=str(petg_overrides["display_name"]),
        )

    pla_overrides = _pla_overrides_for_material(material)
    if pla_overrides is not None:
        filament_settings_id = (
            "Generic PLA+"
            if pla_overrides["variant"] == "pla_plus"
            else DEFAULT_PROFILE_IDS.filament_settings_id
        )
        return _generic_material_bundle_profile_config(
            profile_ids=_profile_ids_with_filament(filament_settings_id),
            filament_profile_fallbacks=(
                GENERIC_PLA_PLUS_FILAMENT_PROFILE_FALLBACKS
                if pla_overrides["variant"] == "pla_plus"
                else GENERIC_PLA_FILAMENT_PROFILE_FALLBACKS
            ),
            material_overrides=pla_overrides,
            printer_settings=printer_settings,
            profiles=profiles,
            material_rule_slug=str(pla_overrides["variant"]),
            material_rule_name=(
                "PLA+" if pla_overrides["variant"] == "pla_plus" else "PLA"
            ),
        )

    abs_asa_rule = _abs_asa_rule_for_material(material)
    if abs_asa_rule is not None:
        filament_settings_id = f"Generic {abs_asa_rule.variant}"
        return _generic_material_bundle_profile_config(
            profile_ids=_profile_ids_with_filament(filament_settings_id),
            filament_profile_fallbacks=_generic_filament_profile_fallbacks(
                filament_settings_id
            ),
            material_overrides={
                "filament_overrides": abs_asa_rule.filament_overrides,
                "process_overrides": abs_asa_rule.process_overrides,
            },
            printer_settings=printer_settings,
            profiles=profiles,
            material_rule_slug=abs_asa_rule.variant.lower(),
            material_rule_name=abs_asa_rule.variant,
        )

    pc_pa_rule = _pc_pa_rule_for_material(material)
    if pc_pa_rule is not None:
        filament_settings_id = f"Generic {pc_pa_rule.material}"
        return _generic_material_bundle_profile_config(
            profile_ids=_profile_ids_with_filament(filament_settings_id),
            filament_profile_fallbacks=_generic_filament_profile_fallbacks(
                filament_settings_id
            ),
            material_overrides={
                "filament_overrides": pc_pa_rule.filament_overrides,
                "process_overrides": pc_pa_rule.process_overrides,
            },
            printer_settings=printer_settings,
            profiles=profiles,
            material_rule_slug=pc_pa_rule.material.lower(),
            material_rule_name=pc_pa_rule.material,
        )

    return BundleProfileConfig(
        profile_ids=DEFAULT_PROFILE_IDS,
        filament_settings=_resolved_bambu_profile_settings(
            DEFAULT_PROFILE_IDS.filament_settings_id,
            *GENERIC_PLA_FILAMENT_PROFILE_FALLBACKS,
            profiles=profiles,
        ),
        process_settings=_resolved_bambu_profile_settings(
            DEFAULT_PROFILE_IDS.print_settings_id,
            DEFAULT_BBL_P2S_PROCESS_PROFILE,
            profiles=profiles,
        ),
        printer_settings=printer_settings,
    )


def _generic_material_bundle_profile_config(
    *,
    profile_ids: BambuProfileIds,
    filament_profile_fallbacks: Sequence[str],
    material_overrides: Mapping[str, Any],
    printer_settings: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    material_rule_slug: str,
    material_rule_name: str,
) -> BundleProfileConfig:
    base_filament_settings = _resolved_bambu_profile_settings(
        profile_ids.filament_settings_id,
        *filament_profile_fallbacks,
        profiles=profiles,
    )
    base_process_settings = _resolved_bambu_profile_settings(
        profile_ids.print_settings_id,
        DEFAULT_BBL_P2S_PROCESS_PROFILE,
        DEFAULT_PROFILE_IDS.print_settings_id,
        profiles=profiles,
    )
    return BundleProfileConfig(
        profile_ids=profile_ids,
        filament_settings={
            **base_filament_settings,
            **dict(material_overrides["filament_overrides"]),
        },
        process_settings={
            **base_process_settings,
            **dict(material_overrides["process_overrides"]),
        },
        printer_settings=printer_settings,
        material_rule_slug=material_rule_slug,
        material_rule_name=material_rule_name,
    )


def _profile_ids_with_filament(filament_settings_id: str) -> BambuProfileIds:
    return BambuProfileIds(
        filament_settings_id=filament_settings_id,
        print_settings_id=DEFAULT_PROFILE_IDS.print_settings_id,
        printer_settings_id=DEFAULT_PROFILE_IDS.printer_settings_id,
        printer_model=DEFAULT_PROFILE_IDS.printer_model,
        printer_variant=DEFAULT_PROFILE_IDS.printer_variant,
        nozzle_diameter=DEFAULT_PROFILE_IDS.nozzle_diameter,
        printable_height=DEFAULT_PROFILE_IDS.printable_height,
    )


def _generic_filament_profile_fallbacks(filament_settings_id: str) -> tuple[str, ...]:
    return (
        f"{filament_settings_id} @BBL P2S",
        f"{filament_settings_id} @base",
    )


def _available_bambu_profiles() -> dict[str, Mapping[str, Any]]:
    profiles: dict[str, Mapping[str, Any]] = {}
    for root in default_bambu_orca_profile_roots():
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json"), key=lambda item: str(item.relative_to(root))):
            try:
                profile = load_profile(path)
            except (OSError, ValueError):
                continue
            name = profile.get("name")
            if isinstance(name, str) and name:
                profiles.setdefault(name, profile)
    return profiles


def _resolved_bambu_profile_settings(
    profile_name: str,
    *fallback_profile_names: str,
    profiles: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    for candidate in (profile_name, *fallback_profile_names):
        profile = profiles.get(candidate)
        if profile is None:
            continue
        try:
            return resolve_inherits(profile, profiles=profiles)
        except (KeyError, ValueError):
            continue
    return {}


def _tpu_rule_for_material(material: str) -> TpuMaterialRule | None:
    normalized = material.lower().replace("_", " ").replace("-", " ")
    if "tpu" not in normalized:
        return None
    if "sunlu" in normalized and "90" in normalized:
        return get_tpu_rule("sunlu-tpu-90a-slipper")
    if "95" in normalized:
        return get_tpu_rule("tpu-95a-foundation")
    return get_tpu_rule("tpu-90a-foundation")


def _petg_overrides_for_material(material: str) -> Mapping[str, Any] | None:
    normalized = material.lower().replace("_", " ").replace("-", " ")
    if "petg" not in normalized:
        return None
    return build_petg_overrides("petg")


def _pla_overrides_for_material(material: str) -> Mapping[str, Any] | None:
    normalized = material.lower().replace("_", " ").replace("-", " ")
    if "pla" not in normalized:
        return None
    if "plus" in normalized or "+" in material:
        return build_pla_overrides("pla+")
    return build_pla_overrides("pla")


def _abs_asa_rule_for_material(material: str) -> AbsAsaMaterialRule | None:
    normalized = material.lower().replace("_", " ").replace("-", " ")
    tokens = set(normalized.split())
    if "abs" in tokens:
        return get_abs_asa_rule("ABS")
    if "asa" in tokens:
        return get_abs_asa_rule("ASA")
    return None


def _pc_pa_rule_for_material(material: str) -> PcPaMaterialRule | None:
    normalized = material.lower().replace("_", "-").replace("/", "-")
    compact = normalized.replace(" ", "-")
    if "pa-cf" in compact or "nylon-cf" in compact:
        return get_pc_pa_material_rule("pa-cf")
    tokens = set(normalized.replace("-", " ").split())
    if "pc" in tokens or "polycarbonate" in tokens:
        return get_pc_pa_material_rule("pc")
    if "pa" in tokens or "nylon" in tokens or "polyamide" in tokens:
        return get_pc_pa_material_rule("pa")
    return None


def _tpu_filament_settings_id(rule: TpuMaterialRule) -> str:
    return _first_setting_value(
        rule.filament_overrides.get("filament_settings_id"),
        fallback=DEFAULT_PROFILE_IDS.filament_settings_id,
    )


def _tpu_print_settings_id(rule: TpuMaterialRule) -> str:
    if rule.slug == "sunlu-tpu-90a-slipper":
        return "0.20mm Slipper TPU 90A @BBL P2S"
    return DEFAULT_PROFILE_IDS.print_settings_id


def _first_setting_value(value: Any, *, fallback: str) -> str:
    if isinstance(value, (list, tuple)) and value:
        return str(value[0])
    if isinstance(value, str) and value:
        return value
    return fallback


def _bundle_object_name(provider_id: str, imported_mesh: Path) -> str:
    if provider_id == "existing_mesh":
        return f"existing_stl_{imported_mesh.stem}"
    return f"generated_mesh_{imported_mesh.stem}"


def _bundle_validation_receipt(bundle_path: Path, validation_path: Path) -> StageReceipt:
    validation = validate_bundle(bundle_path)
    payload = {
        "bundle_path": str(bundle_path),
        "ok": validation.ok,
        "errors": list(validation.errors),
        "application": validation.application,
    }
    validation_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    status = StageStatus.SUCCEEDED if validation.ok else StageStatus.FAILED
    message = (
        "validated Bambu 3MF bundle structure"
        if validation.ok
        else f"Bambu 3MF bundle validation failed: {'; '.join(validation.errors)}"
    )
    return StageReceipt(
        stage="bundle_validation",
        status=status,
        message=message,
        artifacts=(
            Artifact(
                kind=ArtifactKind.REPORT,
                path=validation_path,
                label="Bambu 3MF validation JSON",
                metadata={"format": "json"},
            ),
        ),
        metrics={
            "ok": validation.ok,
            "application": validation.application,
            "error_count": len(validation.errors),
        },
    )


def _slice_not_requested_receipt() -> StageReceipt:
    return StageReceipt(
        stage="slice",
        status=StageStatus.SKIPPED,
        message="Bambu CLI slice not requested; rerun with slice enabled for slice verification.",
        metrics={"slice_requested": False},
    )


def _slice_gate_status(stages: Sequence[StageReceipt]) -> Mapping[str, Any] | None:
    for receipt in reversed(stages):
        if receipt.stage == "slice":
            return {
                "status": receipt.status.value,
                "message": receipt.message,
            }
    return None


def _mesh_output_format(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "stl"


__all__ = [
    "NON_MESH_MESHGEN_MESSAGE",
    "PipelineError",
    "PipelineResult",
    "run_edit_recipe_pipeline",
    "run_existing_mesh_pipeline",
    "run_existing_mesh_pipeline_on_layout",
]
