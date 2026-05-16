from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.contracts import ArtifactKind, StageStatus
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline


def test_existing_mesh_pipeline_imports_mesh_and_writes_reports(tmp_path: Path):
    source = tmp_path / "fixture.stl"
    source.write_bytes(b"solid printpipe\nendsolid printpipe\n")
    runs_dir = tmp_path / "runs"

    result = run_existing_mesh_pipeline(source, runs_dir)

    assert result.layout.root.parent == runs_dir
    assert result.layout.original_input.read_bytes() == source.read_bytes()

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["route_existing_mesh"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].metrics["provider_id"] == "existing_mesh"
    assert stages["meshgen"].metrics["attempt_count"] == 1

    imported_mesh = result.layout.meshgen_dir / "fixture.stl"
    assert imported_mesh.read_bytes() == source.read_bytes()
    assert stages["meshgen"].artifacts[0].kind == ArtifactKind.GENERATED_MESH
    assert stages["meshgen"].artifacts[0].path == imported_mesh

    artifact_paths = {artifact.path for artifact in result.artifacts}
    assert imported_mesh in artifact_paths
    assert result.layout.reports_dir / "run_report.json" in artifact_paths
    assert result.layout.reports_dir / "run_report.md" in artifact_paths
    assert result.layout.reports_dir / "run_report.html" in artifact_paths

    report = json.loads(
        (result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    report_stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("meshgen", "succeeded") in report_stages
    assert report["artifacts"][-1]["kind"] == "generated_mesh"
    assert report["artifacts"][-1]["path"] == "20_meshgen/fixture.stl"
    assert (result.layout.reports_dir / "run_report.html").exists()


def test_existing_mesh_pipeline_rejects_media_inputs_with_reported_failure(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"not a real image yet")
    runs_dir = tmp_path / "runs"

    with pytest.raises(
        PipelineError,
        match="image/video meshgen is not wired into the orchestrator yet",
    ) as raised:
        run_existing_mesh_pipeline(source, runs_dir)

    result = raised.value.result
    assert result.layout.root.parent == runs_dir
    assert result.layout.original_input.read_bytes() == source.read_bytes()
    assert (result.layout.frames_dir / "selected" / "reference.png").exists()

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["extract_references"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.FAILED
    assert stages["meshgen"].message == "image/video meshgen is not wired into the orchestrator yet"
    assert stages["meshgen"].metrics == {"input_kind": "image"}

    report_path = result.layout.reports_dir / "run_report.json"
    assert report_path in {artifact.path for artifact in result.artifacts}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert ("meshgen", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert report["warnings"] == ["image/video meshgen is not wired into the orchestrator yet"]
    assert (result.layout.reports_dir / "run_report.html").exists()
