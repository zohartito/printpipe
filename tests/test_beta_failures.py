from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.failures import (
    FAILURE_REPORT_REQUIRED_HEADINGS,
    FailureArtifact,
    build_failure_report,
    missing_required_headings,
    parse_failure_report_sections,
)


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
