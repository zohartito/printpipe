"""End-to-end PrintPipe pipeline orchestrators."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from printpipe.bambu.slicer import run_bambu_cli_slice_stage
from printpipe.bambu.threemf import BambuProfileIds, GuiSafeTransform, validate_bundle
from printpipe.bambu.threemf.mesh_adapter import write_bundle_from_ascii_stl
from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageReceipt, StageStatus
from printpipe.geometry import (
    BedSize,
    candidate_rotations,
    read_ascii_stl_vertices,
    select_top_orientations,
    write_bed_fit_preview_artifacts,
    write_oriented_ascii_stl_artifacts,
)
from printpipe.inputs import prepare_input
from printpipe.mesh.repair import repair_mesh_file_to_receipt
from printpipe.meshgen import (
    ExistingMeshProvider,
    MeshGenRequest,
    MeshGenResult,
    generate_with_retries,
)
from printpipe.preflight import build_pre_print_checklist
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs import RunLayout, create_run


NON_MESH_MESHGEN_MESSAGE = "image/video meshgen is not wired into the orchestrator yet"
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


@dataclass(frozen=True)
class PipelineResult:
    layout: RunLayout
    stages: tuple[StageReceipt, ...]
    artifacts: tuple[Artifact, ...]


class PipelineError(RuntimeError):
    def __init__(self, message: str, result: PipelineResult) -> None:
        super().__init__(message)
        self.result = result


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
) -> PipelineResult:
    """Run the currently wired pipeline spine for an existing mesh input."""

    layout = create_run(input_path, runs_dir)
    input_result = prepare_input(layout.original_input, layout.frames_dir)
    stages = list(input_result.receipts)

    if input_result.kind != InputKind.MESH:
        failure = StageReceipt(
            stage="meshgen",
            status=StageStatus.FAILED,
            message=NON_MESH_MESHGEN_MESSAGE,
            metrics={"input_kind": input_result.kind.value},
        )
        stages.append(failure)
        result = _write_pipeline_reports(
            layout,
            stages=tuple(stages),
            warnings=(NON_MESH_MESHGEN_MESSAGE,),
            material=material,
            printer=printer,
            use_case=use_case,
            settings_changes=settings_changes,
        )
        raise PipelineError(NON_MESH_MESHGEN_MESSAGE, result)

    if input_result.mesh_artifact is None:
        message = "existing mesh input did not produce a mesh artifact"
        stages.append(
            StageReceipt(
                stage="meshgen",
                status=StageStatus.FAILED,
                message=message,
                metrics={"input_kind": input_result.kind.value},
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

    provider = ExistingMeshProvider()
    request = MeshGenRequest(
        input_kind=InputKind.MESH,
        source_paths=(input_result.mesh_artifact.path,),
        output_formats=(_mesh_output_format(input_result.mesh_artifact.path),),
        max_attempts=1,
    )
    mesh_result = generate_with_retries(provider, request, layout)
    stages.append(_meshgen_stage_receipt(mesh_result))

    warnings = _warnings_for_mesh_result(mesh_result)
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

    object_name = f"existing_stl_{imported_mesh.stem}"
    bundle_path = layout.bundle_dir / f"{object_name}.3mf"
    write_bundle_from_ascii_stl(
        oriented_mesh,
        bundle_path,
        DEFAULT_PROFILE_IDS,
        object_name=object_name,
        transform=GuiSafeTransform.bed_center(DEFAULT_BED.width_mm, DEFAULT_BED.depth_mm),
    )
    stages.append(_bundle_stage_receipt(bundle_path, oriented_mesh, object_name))

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


def _meshgen_stage_receipt(result: MeshGenResult) -> StageReceipt:
    artifacts = (result.artifact,) if result.artifact is not None else ()
    message = "imported existing mesh with ExistingMeshProvider"
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
    pre_print_checklist = build_pre_print_checklist(
        material=material,
        printer=printer,
        use_case=use_case,
        slice_gate_status=_slice_gate_status(stages),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    report_json, report_markdown = write_run_report(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    report_html = write_html_report(layout, report_dict)
    return PipelineResult(
        layout=layout,
        stages=tuple(stages),
        artifacts=(*_stage_artifacts(stages), report_json, report_markdown, report_html),
    )


def _stage_artifacts(stages: Sequence[StageReceipt]) -> tuple[Artifact, ...]:
    return tuple(artifact for stage in stages for artifact in stage.artifacts)


def _warnings_for_mesh_result(result: MeshGenResult) -> tuple[str, ...]:
    if result.status == StageStatus.SUCCEEDED:
        return ()
    if result.error is None:
        return ("existing mesh import failed",)
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


def _bundle_stage_receipt(bundle_path: Path, source_mesh: Path, object_name: str) -> StageReceipt:
    return StageReceipt(
        stage="bundle",
        status=StageStatus.SUCCEEDED,
        message="wrote Bambu 3MF bundle from oriented ASCII STL",
        artifacts=(
            Artifact(
                kind=ArtifactKind.THREEMF,
                path=bundle_path,
                label="Bambu 3MF bundle",
                metadata={
                    "source_mesh": source_mesh,
                    "object_name": object_name,
                    "profile_ids": DEFAULT_PROFILE_IDS,
                },
            ),
        ),
        metrics={
            "source_mesh": source_mesh,
            "bundle_path": bundle_path,
            "object_name": object_name,
        },
    )


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
    "run_existing_mesh_pipeline",
]
