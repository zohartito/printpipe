from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.failures import (
    FAILURE_REPORT_REQUIRED_HEADINGS,
    FailureArtifact,
    build_failure_report,
    missing_required_headings,
    parse_failure_report_sections,
    write_failure_report_files,
)
from printpipe.beta.regression import load_regression_manifest
from printpipe.cli import main


def test_failure_report_serializes_failed_run_context_to_json_friendly_dict(tmp_path: Path):
    slice_log = tmp_path / "runs" / "run-beta-001" / "70_slice" / "slice.log"
    preview = tmp_path / "runs" / "run-beta-001" / "80_reports" / "preview.png"

    report = build_failure_report(
        run_id="run-beta-001",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S 0.4 nozzle",
        failed_stage="slice",
        symptoms=("Bambu Studio reported floating cantilever warnings.", "No 3MF emitted."),
        artifacts=(
            FailureArtifact(label="Slice log", path=slice_log, kind="slice_log"),
            FailureArtifact(label="Preview", path=preview, kind="preview"),
        ),
        reproduction_command="printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --material tpu",
        physical_print_status="not_printed",
    )

    report_dict = report.to_dict()

    assert report_dict == {
        "schema_version": 1,
        "run_id": "run-beta-001",
        "input_type": "existing_stl",
        "material": "SUNLU TPU 90A",
        "printer": "Bambu Lab P2S 0.4 nozzle",
        "failed_stage": "slice",
        "symptoms": [
            "Bambu Studio reported floating cantilever warnings.",
            "No 3MF emitted.",
        ],
        "artifacts": [
            {
                "label": "Slice log",
                "path": str(slice_log),
                "kind": "slice_log",
                "notes": "",
            },
            {
                "label": "Preview",
                "path": str(preview),
                "kind": "preview",
                "notes": "",
            },
        ],
        "reproduction_command": (
            "printpipe run tests/fixtures/objects/flat_bracket/flat_bracket.stl --material tpu"
        ),
        "physical_print_status": "not_printed",
    }
    json.dumps(report_dict)


def test_parse_failure_report_sections_returns_required_heading_bodies():
    markdown = """# PrintPipe Beta Failure Report

## Run Context
- Run ID: run-beta-001

## Failure Details
- Failed stage: slice

## Symptoms
- Floating cantilever warning

## Artifacts
- 70_slice/slice.log

## Reproduction
```bash
printpipe run input.stl
```

## Physical Print Status
- Not printed

## Triage Notes
- Needs support review
"""

    sections = parse_failure_report_sections(markdown)

    assert sections["Run Context"].strip() == "- Run ID: run-beta-001"
    assert sections["Failure Details"].strip() == "- Failed stage: slice"
    assert sections["Symptoms"].strip() == "- Floating cantilever warning"
    assert sections["Artifacts"].strip() == "- 70_slice/slice.log"
    assert "printpipe run input.stl" in sections["Reproduction"]
    assert sections["Physical Print Status"].strip() == "- Not printed"
    assert sections["Triage Notes"].strip() == "- Needs support review"
    assert missing_required_headings(markdown) == []


def test_failure_report_template_contains_required_headings():
    template_path = Path("docs/beta/failure_report_template.md")
    template = template_path.read_text(encoding="utf-8")

    assert missing_required_headings(template) == []
    for heading in FAILURE_REPORT_REQUIRED_HEADINGS:
        assert f"## {heading}" in template


def test_write_failure_report_files_copies_artifacts_and_renders_required_markdown(
    tmp_path: Path,
):
    run_root = tmp_path / "runs" / "run-beta-001"
    artifact_source = run_root / "70_slice" / "slice failure.log"
    artifact_source.parent.mkdir(parents=True)
    artifact_source.write_text("floating cantilever warning", encoding="utf-8")
    report = build_failure_report(
        run_id="run-beta-001",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        failed_stage="slice",
        symptoms=("floating cantilever warning",),
        artifacts=(
            FailureArtifact(
                label="Slice log",
                path=artifact_source,
                kind="slice_log",
            ),
        ),
        reproduction_command="printpipe run input.stl --material tpu",
        physical_print_status="not_printed",
    )

    result = write_failure_report_files(
        run_root=run_root,
        report=report,
        copy_artifacts=True,
    )

    report_json = Path(result["json_path"])
    report_markdown = Path(result["markdown_path"])
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    markdown = report_markdown.read_text(encoding="utf-8")

    assert report_json == run_root / "90_beta" / "failure_report.json"
    assert report_markdown == run_root / "90_beta" / "failure_report.md"
    assert payload["artifacts"] == [
        {
            "label": "Slice log",
            "path": "90_beta/artifacts/slice-failure.log",
            "kind": "slice_log",
            "notes": "",
        }
    ]
    assert (run_root / "90_beta" / "artifacts" / "slice-failure.log").read_text(
        encoding="utf-8"
    ) == "floating cantilever warning"
    assert result["missing_required_headings"] == []
    assert missing_required_headings(markdown) == []
    assert "## Reproduction" in markdown
    assert "printpipe run input.stl --material tpu" in markdown


def test_cli_record_beta_failure_writes_packet_and_regression_case(
    tmp_path: Path,
    capsys,
):
    run_root = tmp_path / "runs" / "run-beta-001"
    input_dir = run_root / "00_input"
    artifact_source = run_root / "70_slice" / "slice.log"
    input_dir.mkdir(parents=True)
    artifact_source.parent.mkdir(parents=True)
    (input_dir / "part.stl").write_text("solid part\nendsolid part\n", encoding="utf-8")
    artifact_source.write_text("slice failed", encoding="utf-8")
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-beta-001",
                "input": {"stored_path": "00_input/part.stl"},
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "regressions" / "failure_manifest.json"

    exit_code = main(
        [
            "record-beta-failure",
            str(run_root),
            "--input-type",
            "existing_stl",
            "--material",
            "SUNLU TPU 90A",
            "--printer",
            "Bambu Lab P2S",
            "--failed-stage",
            "slice",
            "--symptom",
            "slice failed",
            "--artifact",
            f"Slice log|slice_log|{artifact_source}|Bambu CLI stderr",
            "--reproduction-command",
            "printpipe run 00_input/part.stl --material tpu",
            "--physical-print-status",
            "not_printed",
            "--regression-manifest",
            str(manifest_path),
            "--case-id",
            "run-beta-001-slice",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    failure_payload = json.loads(
        (run_root / "90_beta" / "failure_report.json").read_text(encoding="utf-8")
    )
    regression_manifest = load_regression_manifest(manifest_path)

    assert exit_code == 0
    assert payload["json_path"].endswith("90_beta/failure_report.json")
    assert payload["regression_manifest_path"] == str(manifest_path)
    assert payload["regression_case_id"] == "run-beta-001-slice"
    assert failure_payload["symptoms"] == ["slice failed"]
    assert failure_payload["artifacts"][0]["path"] == "90_beta/artifacts/slice.log"
    assert regression_manifest.cases[0].case_id == "run-beta-001-slice"
    assert regression_manifest.cases[0].source_run_id == "run-beta-001"
    assert regression_manifest.cases[0].fixture_path == input_dir / "part.stl"
    assert regression_manifest.cases[0].command == (
        "printpipe",
        "run",
        "00_input/part.stl",
        "--material",
        "tpu",
    )
