"""End-to-end PrintPipe pipeline orchestrators."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from printpipe.contracts import Artifact, InputKind, StageReceipt, StageStatus
from printpipe.inputs import prepare_input
from printpipe.meshgen import (
    ExistingMeshProvider,
    MeshGenRequest,
    MeshGenResult,
    generate_with_retries,
)
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs import RunLayout, create_run


NON_MESH_MESHGEN_MESSAGE = "image/video meshgen is not wired into the orchestrator yet"


@dataclass(frozen=True)
class PipelineResult:
    layout: RunLayout
    stages: tuple[StageReceipt, ...]
    artifacts: tuple[Artifact, ...]


class PipelineError(RuntimeError):
    def __init__(self, message: str, result: PipelineResult) -> None:
        super().__init__(message)
        self.result = result


def run_existing_mesh_pipeline(input_path: Path, runs_dir: Path = Path("runs")) -> PipelineResult:
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
        result = _write_pipeline_reports(layout, stages=tuple(stages), warnings=(message,))
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
    result = _write_pipeline_reports(layout, stages=tuple(stages), warnings=warnings)
    if mesh_result.status != StageStatus.SUCCEEDED:
        message = (
            mesh_result.error.message
            if mesh_result.error is not None
            else "existing mesh import failed"
        )
        raise PipelineError(message, result)

    return result


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
) -> PipelineResult:
    report_dict = build_run_report_dict(layout, stages=stages, warnings=warnings)
    report_json, report_markdown = write_run_report(layout, stages=stages, warnings=warnings)
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


def _mesh_output_format(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "stl"


__all__ = [
    "NON_MESH_MESHGEN_MESSAGE",
    "PipelineError",
    "PipelineResult",
    "run_existing_mesh_pipeline",
]
