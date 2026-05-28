from __future__ import annotations

from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs.paths import create_run
from printpipe.web.status import build_run_status


def test_build_run_status_summarizes_reported_run(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-001")
    mesh_path = layout.meshgen_dir / "mesh.stl"
    mesh_path.write_text("solid fake\nendsolid fake\n", encoding="utf-8")

    stages = (
        StageReceipt(
            stage="classify_input",
            status=StageStatus.SUCCEEDED,
            message="Input classified.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.ORIGINAL_INPUT,
                    path=layout.original_input,
                    label="Original input",
                ),
            ),
        ),
        StageReceipt(
            stage="meshgen",
            status=StageStatus.FAILED,
            message="Provider returned a non-manifold mesh.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=mesh_path,
                    label="Generated mesh",
                ),
            ),
        ),
    )
    warnings = ("non-manifold edge warning", "slice gate did not run")
    report_dict = build_run_report_dict(layout, stages=stages, warnings=warnings)
    write_run_report(layout, stages=stages, warnings=warnings)
    write_html_report(layout, report_dict)

    status = build_run_status(layout.root)

    assert status["schema_version"] == 1
    assert status["run_id"] == "run-001"
    assert status["manifest"]["present"] is True
    assert status["report"]["state"] == "present"
    assert status["report"]["json"]["present"] is True
    assert status["report"]["markdown"]["present"] is True
    assert status["report"]["html"]["present"] is True
    assert status["warning_count"] == 2
    assert status["warnings"] == list(warnings)
    assert status["artifacts_present"] is True
    assert status["artifact_count"] == 2
    assert status["missing_artifact_count"] == 0
    assert [
        (stage["name"], stage["status"], stage["artifact_count"], stage["artifacts_present"])
        for stage in status["stages"]
    ] == [
        ("classify_input", "succeeded", 1, True),
        ("meshgen", "failed", 1, True),
    ]
    assert status["progress"] == {
        "state": "failed",
        "total": 2,
        "complete": 2,
        "failed": 1,
        "running": 0,
        "pending": 0,
        "percent": 100,
    }


def test_build_run_status_marks_manifest_only_run_as_missing_report(tmp_path: Path):
    source = tmp_path / "part.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="run-002")

    status = build_run_status(layout.root)

    assert status["run_id"] == "run-002"
    assert status["input"]["kind"] == "mesh"
    assert status["report"]["state"] == "missing"
    assert status["report"]["json"]["present"] is False
    assert status["report"]["markdown"]["present"] is False
    assert status["report"]["html"]["present"] is False
    assert status["warning_count"] == 0
    assert status["artifacts_present"] is False
    assert status["artifact_count"] == 0
    assert [
        (stage["name"], stage["status"], stage["artifact_count"])
        for stage in status["stages"]
    ] == [
        ("input", "unknown", 0),
        ("frames", "unknown", 0),
        ("meshgen", "unknown", 0),
        ("repair", "unknown", 0),
        ("geometry", "unknown", 0),
        ("profiles", "unknown", 0),
        ("bundle", "unknown", 0),
        ("slice", "unknown", 0),
        ("reports", "unknown", 0),
    ]
    assert status["progress"] == {
        "state": "missing_report",
        "total": 9,
        "complete": 0,
        "failed": 0,
        "running": 0,
        "pending": 9,
        "percent": 0,
    }


def test_build_run_status_reports_unreadable_external_artifacts_without_crashing(
    monkeypatch,
    tmp_path: Path,
):
    source = tmp_path / "part.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="run-external-artifact")
    external_artifact = tmp_path / "external" / "mesh.stl"
    external_artifact.parent.mkdir()
    external_artifact.write_text("solid fake\nendsolid fake\n", encoding="utf-8")

    stages = (
        StageReceipt(
            stage="external_mesh",
            status=StageStatus.SUCCEEDED,
            message="External mesh recorded.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=external_artifact,
                    label="External generated mesh",
                ),
            ),
        ),
    )
    report_dict = build_run_report_dict(layout, stages=stages)
    write_run_report(layout, stages=stages)
    write_html_report(layout, report_dict)

    def fake_can_read(path: Path) -> bool:
        return path != external_artifact.resolve()

    monkeypatch.setattr("printpipe.web.status._can_read_path", fake_can_read)

    status = build_run_status(layout.root)

    artifact = status["artifacts"][0]
    assert artifact["path"] == str(external_artifact.resolve())
    assert artifact["present"] is True
    assert artifact["inside_run_root"] is False
    assert artifact["readable"] is False
    assert artifact["state"] == "unreadable"
    assert status["missing_artifact_count"] == 1


def test_build_run_status_marks_unreadable_report_state(
    monkeypatch,
    tmp_path: Path,
):
    source = tmp_path / "part.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="run-unreadable-report")

    def fake_read_json_document(path: Path):
        if path.name == "manifest.json":
            return {
                "run_id": layout.run_id,
                "input": {"kind": "mesh"},
                "stages": {},
            }, "present"
        return None, "unreadable"

    monkeypatch.setattr(
        "printpipe.web.status._read_json_document",
        fake_read_json_document,
    )

    status = build_run_status(layout.root)

    assert status["report"]["state"] == "unreadable"
    assert status["progress"]["state"] == "unreadable_report"
