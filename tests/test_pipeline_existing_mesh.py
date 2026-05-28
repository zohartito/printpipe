from __future__ import annotations

import json
from pathlib import Path

import pytest

import printpipe.pipeline as pipeline_module
from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.meshgen import MeshGenCost, MeshGenResult, MeshGenTiming
from printpipe.pipeline import PipelineError, run_edit_recipe_pipeline, run_existing_mesh_pipeline
from printpipe.runs.editing import EditRecipe, EditScale, EditTargets, GeometryIntent, create_edit_run


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
    assert stages["geometry.write_run_detail_model_preview_artifacts"].status == (
        StageStatus.SUCCEEDED
    )
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
    model_preview_svg = result.layout.geometry_dir / "run_detail_model_preview.svg"
    model_preview_json = result.layout.geometry_dir / "run_detail_model_preview.json"
    bundle = result.layout.bundle_dir / "existing_stl_tiny_tetrahedron.3mf"
    bundle_validation = result.layout.bundle_dir / "existing_stl_tiny_tetrahedron_bundle_validation.json"

    artifact_paths = {artifact.path for artifact in result.artifacts}
    assert imported_mesh in artifact_paths
    assert repaired_mesh in artifact_paths
    assert repair_stats in artifact_paths
    assert oriented_mesh in artifact_paths
    assert bed_fit_svg in artifact_paths
    assert bed_fit_json in artifact_paths
    assert model_preview_svg in artifact_paths
    assert model_preview_json in artifact_paths
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
    assert ("geometry.write_run_detail_model_preview_artifacts", "succeeded") in report_stages
    assert ("bundle", "succeeded") in report_stages
    assert ("bundle_validation", "succeeded") in report_stages
    assert ("slice", "skipped") in report_stages
    report_artifacts = {(artifact["kind"], artifact["path"]) for artifact in report["artifacts"]}
    assert ("generated_mesh", "20_meshgen/tiny_tetrahedron.stl") in report_artifacts
    assert ("repaired_mesh", "30_repair/tiny_tetrahedron_repaired.stl") in report_artifacts
    assert ("oriented_mesh", "40_geometry/tiny_tetrahedron_oriented.stl") in report_artifacts
    assert ("preview", "40_geometry/run_detail_model_preview.svg") in report_artifacts
    assert ("report", "40_geometry/run_detail_model_preview.json") in report_artifacts
    assert ("3mf", "60_bundle/existing_stl_tiny_tetrahedron.3mf") in report_artifacts
    assert report["pre_print_checklist"]
    assert {item["id"] for item in report["pre_print_checklist"]} >= {"slice_gate", "layer_preview"}
    assert (result.layout.reports_dir / "run_report.html").exists()


def test_edit_recipe_pipeline_rebuilds_child_run_without_touching_parent(tmp_path: Path):
    parent = run_existing_mesh_pipeline(STL_FIXTURE, tmp_path / "runs")
    parent_bundle = parent.layout.bundle_dir / "existing_stl_tiny_tetrahedron.3mf"
    parent_bundle_bytes = parent_bundle.read_bytes()
    recipe = EditRecipe(
        parent_run_id=parent.layout.run_id,
        scale=EditScale(y=1.25),
        targets_mm=EditTargets(length=60.0, width=40.0),
        geometry_intent=GeometryIntent(opening_width_delta_mm=8.0),
        support_strategy="snug_tree_auto",
        instruction="widen the opening without changing the sole length",
    )
    edit_layout = create_edit_run(parent.layout.root, recipe)

    result = run_edit_recipe_pipeline(edit_layout.root)

    assert result.layout.root == edit_layout.root
    assert parent_bundle.read_bytes() == parent_bundle_bytes
    assert (edit_layout.bundle_dir / "existing_stl_tiny_tetrahedron_edit_recipe_source.3mf").exists()
    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["edit_recipe.source_mesh"].status == StageStatus.SUCCEEDED
    assert stages["geometry.apply_edit_recipe"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["bundle"].status == StageStatus.SUCCEEDED

    report = json.loads((edit_layout.reports_dir / "run_report.json").read_text(encoding="utf-8"))
    assert ("geometry.apply_edit_recipe", "succeeded") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert any(
        "deterministic rebuild applied scale fields only" in warning
        for warning in report["warnings"]
    )
    assert report["settings_changes"][0]["edit_recipe"]["scale"]["y"] == 1.25
    assert report["settings_changes"][0]["edit_recipe"]["support_strategy"] == "snug_tree_auto"


def test_edit_recipe_pipeline_warns_for_recorded_but_unapplied_edit_fields(
    tmp_path: Path,
):
    parent = run_existing_mesh_pipeline(STL_FIXTURE, tmp_path / "runs")
    recipe = EditRecipe(
        parent_run_id=parent.layout.run_id,
        targets_mm=EditTargets(length=60.0, width=40.0),
        support_strategy="snug_tree_auto",
        instruction="make the opening roomier",
    )
    edit_layout = create_edit_run(parent.layout.root, recipe)

    result = run_edit_recipe_pipeline(edit_layout.root)

    report = json.loads((result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8"))
    warnings = "\n".join(report["warnings"])
    assert "target dimensions are recorded for review" in warnings
    assert "support strategy is recorded for bundling/review" in warnings
    assert "freeform instruction is recorded for review" in warnings


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
            message="Bambu CLI slice failed: slicer terminated by signal 11 (SIGSEGV).",
            artifacts=(Artifact(ArtifactKind.SLICE_LOG, slice_result, "Slice result JSON"),),
            metrics={
                "slice_requested": True,
                "return_code": -11,
                "errors": ("slicer terminated by signal 11 (SIGSEGV)",),
            },
        )

    monkeypatch.setattr(pipeline_module, "run_bambu_cli_slice_stage", fake_slice_stage)

    with pytest.raises(PipelineError, match="slicer terminated by signal 11") as raised:
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
    assert "Bambu CLI slice failed: slicer terminated by signal 11 (SIGSEGV)." in (
        report["warnings"]
    )
    checklist = {item["id"]: item for item in report["pre_print_checklist"]}
    assert checklist["slice_gate"]["status"] == "failed"


def test_existing_mesh_pipeline_rejects_media_inputs_with_reported_failure(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"not a real image yet")
    runs_dir = tmp_path / "runs"

    with pytest.raises(
        PipelineError,
        match="Hunyuan3D local command is not configured",
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
    assert stages["meshgen"].message == (
        "Hunyuan3D local command is not configured; set "
        "PRINTPIPE_HUNYUAN3D_COMMAND or pass a command path."
    )
    assert stages["meshgen"].metrics["provider_id"] == "hunyuan3d"
    assert stages["meshgen"].metrics["attempt_count"] == 1
    assert "mesh_repair" not in stages
    assert "bundle" not in stages

    report_path = result.layout.reports_dir / "run_report.json"
    assert report_path in {artifact.path for artifact in result.artifacts}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert ("meshgen", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert report["warnings"] == [
        "Hunyuan3D local command is not configured; set "
        "PRINTPIPE_HUNYUAN3D_COMMAND or pass a command path."
    ]
    assert (result.layout.reports_dir / "run_report.html").exists()


def test_media_pipeline_uses_configured_meshgen_then_repairs_orients_and_bundles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeMediaMeshProvider:
        provider_id = "hunyuan3d"
        display_name = "Fake Hunyuan3D"

        def generate(self, request, run) -> MeshGenResult:
            assert request.input_kind.value == "image"
            assert tuple(path.name for path in request.source_paths) == ("reference.png",)
            assert tuple(path.name for path in request.reference_images) == ("reference.png",)
            assert request.output_formats[0] == "stl"

            output = run.meshgen_dir / "hunyuan3d.stl"
            output.write_text(STL_FIXTURE.read_text(encoding="ascii"), encoding="ascii")
            return MeshGenResult(
                status=StageStatus.SUCCEEDED,
                provider_id=self.provider_id,
                timing=MeshGenTiming(wall_seconds=3.5),
                cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
                artifact=Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=output,
                    label="Generated mesh from Hunyuan3D",
                ),
                normalized_mesh_path=output,
            )

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

    source = tmp_path / "reference.png"
    source.write_bytes(b"not a real image yet")

    result = run_existing_mesh_pipeline(
        source,
        tmp_path / "runs",
        meshgen_provider=FakeMediaMeshProvider(),
    )

    stages = {receipt.stage: receipt for receipt in result.stages}
    assert stages["classify_input"].status == StageStatus.SUCCEEDED
    assert stages["extract_references"].status == StageStatus.SUCCEEDED
    assert stages["select_references"].status == StageStatus.SUCCEEDED
    assert stages["contact_sheet"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].status == StageStatus.SUCCEEDED
    assert stages["meshgen"].metrics["provider_id"] == "hunyuan3d"
    assert stages["mesh_repair"].status == StageStatus.SUCCEEDED
    assert stages["geometry.write_oriented_ascii_stl_artifacts"].status == StageStatus.SUCCEEDED
    assert stages["bundle"].status == StageStatus.SUCCEEDED
    assert stages["bundle_validation"].status == StageStatus.SUCCEEDED

    report = json.loads(
        (result.layout.reports_dir / "run_report.json").read_text(encoding="utf-8")
    )
    report_artifacts = {(artifact["kind"], artifact["path"]) for artifact in report["artifacts"]}
    assert ("generated_mesh", "20_meshgen/hunyuan3d.stl") in report_artifacts
    assert ("repaired_mesh", "30_repair/hunyuan3d_repaired.stl") in report_artifacts
    assert ("3mf", "60_bundle/generated_mesh_hunyuan3d.3mf") in report_artifacts


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
