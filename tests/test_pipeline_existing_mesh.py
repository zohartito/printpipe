from __future__ import annotations

import json
from pathlib import Path

import pytest

import printpipe.pipeline as pipeline_module
from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "objects" / "existing_stl_pipeline"
STL_FIXTURE = FIXTURE_DIR / "tiny_tetrahedron.stl"


def test_existing_mesh_pipeline_imports_repairs_orients_bundles_and_writes_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_repair_mesh_file_to_receipt(
        input_path: Path | str,
        output_path: Path | str,
        *,
        stats_path: Path | str | None = None,
        allow_non_watertight: bool = False,
        stage: str = "mesh_repair",
    ) -> StageReceipt:
        del allow_non_watertight
        output = Path(output_path)
        stats = Path(stats_path) if stats_path is not None else output.with_suffix(".json")
        output.write_text(Path(input_path).read_text(encoding="ascii"), encoding="ascii")
        stats.write_text(
            json.dumps({"stage": stage, "status": "succeeded"}) + "\n",
            encoding="utf-8",
        )
        return StageReceipt(
            stage=stage,
            status=StageStatus.SUCCEEDED,
            message="fake repair succeeded",
            artifacts=(
                Artifact(ArtifactKind.REPAIRED_MESH, output, "Repaired mesh"),
                Artifact(ArtifactKind.REPORT, stats, "Mesh repair stats JSON"),
            ),
            metrics={"watertight_after": True},
        )

    monkeypatch.setattr(
        pipeline_module,
        "repair_mesh_file_to_receipt",
        fake_repair_mesh_file_to_receipt,
        raising=False,
    )

    runs_dir = tmp_path / "runs"
    result = run_existing_mesh_pipeline(STL_FIXTURE, runs_dir)

    assert result.layout.root.parent == runs_dir
    assert result.layout.original_input.read_bytes() == STL_FIXTURE.read_bytes()

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["route_existing_mesh"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].metrics["provider_id"] == "existing_mesh"
    assert stages["meshgen"].metrics["attempt_count"] == 1
    assert stages["mesh_repair"].status == StageStatus.SUCCEEDED
    assert stages["geometry.write_oriented_ascii_stl_artifacts"].status == StageStatus.SUCCEEDED
    assert stages["geometry.write_bed_fit_preview_artifacts"].status == StageStatus.SUCCEEDED
    assert stages["bundle"].status == StageStatus.SUCCEEDED
    assert stages["bundle_validation"].status == StageStatus.SUCCEEDED
    assert stages["slice"].status == StageStatus.SKIPPED
    assert stages["slice"].metrics == {"slice_requested": False}

    imported_mesh = result.layout.meshgen_dir / STL_FIXTURE.name
    assert imported_mesh.read_bytes() == STL_FIXTURE.read_bytes()
    assert stages["meshgen"].artifacts[0].kind == ArtifactKind.GENERATED_MESH
    assert stages["meshgen"].artifacts[0].path == imported_mesh

    repaired_mesh = result.layout.repair_dir / "tiny_tetrahedron_repaired.stl"
    repair_stats = result.layout.repair_dir / "tiny_tetrahedron_repair.json"
    oriented_mesh = result.layout.geometry_dir / "tiny_tetrahedron_oriented.stl"
    bed_fit_svg = result.layout.reports_dir / "bed_fit.svg"
    bed_fit_json = result.layout.reports_dir / "bed_fit.json"
    bundle = result.layout.bundle_dir / "existing_stl_tiny_tetrahedron.3mf"
    bundle_validation = result.layout.bundle_dir / "existing_stl_tiny_tetrahedron_bundle_validation.json"

    artifact_paths = {artifact.path for artifact in result.artifacts}
    assert imported_mesh in artifact_paths
    assert repaired_mesh in artifact_paths
    assert repair_stats in artifact_paths
    assert oriented_mesh in artifact_paths
    assert bed_fit_svg in artifact_paths
    assert bed_fit_json in artifact_paths
    assert bundle in artifact_paths
    assert bundle_validation in artifact_paths
    assert result.layout.reports_dir / "run_report.json" in artifact_paths
    assert result.layout.reports_dir / "run_report.md" in artifact_paths
    assert result.layout.reports_dir / "run_report.html" in artifact_paths

    report = json.loads(
        (result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    report_stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("meshgen", "succeeded") in report_stages
    assert ("mesh_repair", "succeeded") in report_stages
    assert ("geometry.write_oriented_ascii_stl_artifacts", "succeeded") in report_stages
    assert ("geometry.write_bed_fit_preview_artifacts", "succeeded") in report_stages
    assert ("bundle", "succeeded") in report_stages
    assert ("bundle_validation", "succeeded") in report_stages
    assert ("slice", "skipped") in report_stages
    report_artifacts = {(artifact["kind"], artifact["path"]) for artifact in report["artifacts"]}
    assert ("generated_mesh", "20_meshgen/tiny_tetrahedron.stl") in report_artifacts
    assert ("repaired_mesh", "30_repair/tiny_tetrahedron_repaired.stl") in report_artifacts
    assert ("oriented_mesh", "40_geometry/tiny_tetrahedron_oriented.stl") in report_artifacts
    assert ("3mf", "60_bundle/existing_stl_tiny_tetrahedron.3mf") in report_artifacts
    assert report["pre_print_checklist"]
    assert {item["id"] for item in report["pre_print_checklist"]} >= {"slice_gate", "layer_preview"}
    assert (result.layout.reports_dir / "run_report.html").exists()


def test_existing_mesh_pipeline_runs_requested_slice_and_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_slice_stage(**kwargs) -> StageReceipt:
        run_layout = kwargs["run_layout"]
        slice_result = run_layout.slice_dir / "slice_result.json"
        slice_result.parent.mkdir(parents=True, exist_ok=True)
        slice_result.write_text('{"return_code": 0}\n', encoding="utf-8")
        return StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Bambu CLI slice passed.",
            artifacts=(Artifact(ArtifactKind.SLICE_LOG, slice_result, "Slice result JSON"),),
            metrics={
                "slice_requested": True,
                "return_code": 0,
                "time_seconds": 3723,
                "filament_g": 12.5,
            },
        )

    monkeypatch.setattr(pipeline_module, "run_bambu_cli_slice_stage", fake_slice_stage)

    result = run_existing_mesh_pipeline(STL_FIXTURE, tmp_path / "runs", run_slice=True)

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["slice"].status == StageStatus.SUCCEEDED
    assert stages["slice"].metrics["slice_requested"] is True

    report = json.loads(
        (result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    assert ("slice", "succeeded") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert ("slice_log", "70_slice/slice_result.json") in {
        (artifact["kind"], artifact["path"]) for artifact in report["artifacts"]
    }
    checklist = {item["id"]: item for item in report["pre_print_checklist"]}
    assert checklist["slice_gate"]["status"] == "passed"


def test_existing_mesh_pipeline_preserves_requested_slice_failure_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_slice_stage(**kwargs) -> StageReceipt:
        run_layout = kwargs["run_layout"]
        slice_result = run_layout.slice_dir / "slice_result.json"
        slice_result.parent.mkdir(parents=True, exist_ok=True)
        slice_result.write_text('{"return_code": -11}\n', encoding="utf-8")
        return StageReceipt(
            stage="slice",
            status=StageStatus.FAILED,
            message="Bambu CLI slice failed.",
            artifacts=(Artifact(ArtifactKind.SLICE_LOG, slice_result, "Slice result JSON"),),
            metrics={
                "slice_requested": True,
                "return_code": -11,
                "errors": ("slicer terminated by signal 11 (SIGSEGV)",),
            },
        )

    monkeypatch.setattr(pipeline_module, "run_bambu_cli_slice_stage", fake_slice_stage)

    with pytest.raises(PipelineError, match="Bambu CLI slice failed.") as raised:
        run_existing_mesh_pipeline(STL_FIXTURE, tmp_path / "runs", run_slice=True)

    result = raised.value.result
    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["slice"].status == StageStatus.FAILED
    assert stages["slice"].metrics["slice_requested"] is True

    report = json.loads(
        (result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    assert ("slice", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert ("slice_log", "70_slice/slice_result.json") in {
        (artifact["kind"], artifact["path"]) for artifact in report["artifacts"]
    }
    assert "Bambu CLI slice failed." in report["warnings"]
    checklist = {item["id"]: item for item in report["pre_print_checklist"]}
    assert checklist["slice_gate"]["status"] == "failed"


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
    assert "mesh_repair" not in stages
    assert "bundle" not in stages

    report_path = result.layout.reports_dir / "run_report.json"
    assert report_path in {artifact.path for artifact in result.artifacts}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert ("meshgen", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert report["warnings"] == ["image/video meshgen is not wired into the orchestrator yet"]
    assert (result.layout.reports_dir / "run_report.html").exists()


def test_existing_mesh_pipeline_fails_before_orientation_when_repair_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_failed_repair(
        input_path: Path | str,
        output_path: Path | str,
        *,
        stats_path: Path | str | None = None,
        allow_non_watertight: bool = False,
        stage: str = "mesh_repair",
    ) -> StageReceipt:
        del input_path, output_path, stats_path, allow_non_watertight
        return StageReceipt(
            stage=stage,
            status=StageStatus.FAILED,
            message="repair failed: still non-watertight",
            metrics={"watertight_after": False},
        )

    monkeypatch.setattr(
        pipeline_module,
        "repair_mesh_file_to_receipt",
        fake_failed_repair,
        raising=False,
    )

    with pytest.raises(PipelineError, match="repair failed: still non-watertight") as raised:
        run_existing_mesh_pipeline(STL_FIXTURE, tmp_path / "runs")

    stages = {receipt.stage: receipt for receipt in raised.value.result.stages}
    assert stages["mesh_repair"].status == StageStatus.FAILED
    assert "geometry.write_oriented_ascii_stl_artifacts" not in stages
    assert "bundle" not in stages

    report = json.loads(
        (raised.value.result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    assert ("mesh_repair", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert report["warnings"] == ["mesh_repair: repair failed: still non-watertight"]
