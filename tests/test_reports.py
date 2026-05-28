from __future__ import annotations

import json
from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import stage_receipt_to_dict, write_run_report
from printpipe.runs.paths import create_run


def test_stage_receipt_serializes_to_json_friendly_dict(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-001")
    slice_log = layout.slice_dir / "slice.log"
    slice_log.write_text("slice ok\n", encoding="utf-8")

    receipt = StageReceipt(
        stage="slice",
        status=StageStatus.SUCCEEDED,
        message="Bambu CLI slice passed.",
        artifacts=(
            Artifact(
                kind=ArtifactKind.SLICE_LOG,
                path=slice_log,
                label="Raw slice log",
                metadata={"return_code": 0, "source": layout.original_input},
            ),
        ),
        metrics={"layers": 425, "warnings": ("minor internal log line",)},
    )

    receipt_dict = stage_receipt_to_dict(receipt, run_root=layout.root)

    assert receipt_dict == {
        "stage": "slice",
        "status": "succeeded",
        "message": "Bambu CLI slice passed.",
        "artifacts": [
            {
                "kind": "slice_log",
                "path": "70_slice/slice.log",
                "label": "Raw slice log",
                "metadata": {
                    "return_code": 0,
                    "source": "00_input/reference.png",
                },
            }
        ],
        "metrics": {"layers": 425, "warnings": ["minor internal log line"]},
    }
    json.dumps(receipt_dict)


def test_write_run_report_writes_json_and_markdown_to_reports_dir(tmp_path: Path):
    source = tmp_path / "reference.gif"
    source.write_bytes(b"fake gif")
    layout = create_run(source, tmp_path / "runs", run_id="run-002")
    preview = layout.reports_dir / "preview.png"
    preview.write_bytes(b"fake preview")

    receipt = StageReceipt(
        stage="input",
        status=StageStatus.SUCCEEDED,
        message="Stored original input.",
        artifacts=(
            Artifact(
                kind=ArtifactKind.ORIGINAL_INPUT,
                path=layout.original_input,
                label="Original GIF",
            ),
            Artifact(
                kind=ArtifactKind.PREVIEW,
                path=preview,
                label="Preview image",
            ),
        ),
    )

    report_artifacts = write_run_report(
        layout,
        stages=(receipt,),
        warnings=("Slice gate has not run yet.",),
    )

    report_paths = {artifact.label: artifact.path for artifact in report_artifacts}
    json_path = layout.reports_dir / "run_report.json"
    markdown_path = layout.reports_dir / "run_report.md"
    assert report_paths == {
        "Run report JSON": json_path,
        "Run report Markdown": markdown_path,
    }

    report_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert report_json["run_id"] == "run-002"
    assert report_json["stages"][0]["artifacts"][0]["path"] == "00_input/reference.gif"
    assert report_json["warnings"] == ["Slice gate has not run yet."]
    assert report_json["settings_changes"] == []
    assert report_json["pre_print_checklist"] == []

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# PrintPipe Run Report: run-002" in markdown
    assert "## Stages" in markdown
    assert "input" in markdown
    assert "succeeded" in markdown
    assert "Original GIF" in markdown
    assert "](../00_input/reference.gif)" in markdown
    assert "](preview.png)" in markdown
    assert "Slice gate has not run yet." in markdown
    assert "## Settings Changes" in markdown
    assert "No settings changes recorded yet." in markdown
    assert "## Pre-print Checklist" in markdown
    assert "No pre-print checklist recorded for this report." in markdown
    assert "pending final slice gate integration" not in markdown


def test_write_run_report_promotes_prompt_reference_quote_in_markdown(tmp_path: Path):
    source = tmp_path / "prompt.txt"
    source.write_text("small ergonomic wall hook\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="run-prompt-report")
    receipt = StageReceipt(
        stage="prompt_reference_generation",
        status=StageStatus.FAILED,
        message="OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD",
        metrics={
            "provider": "openai",
            "provider_quote": {
                "provider": "openai",
                "privacy_mode": "remote_api",
                "estimated_seconds": 45.0,
                "estimated_cost_usd": 0.25,
                "max_cost_usd": 0.05,
                "remote_upload": True,
                "stores_prompt_with_provider": True,
            },
        },
    )

    write_run_report(layout, stages=(receipt,))

    markdown = (layout.reports_dir / "run_report.md").read_text(encoding="utf-8")
    assert "## Prompt Reference" in markdown
    assert "- Provider: openai" in markdown
    assert "- Status: failed" in markdown
    assert "- Privacy: remote_api" in markdown
    assert "- Estimated cost: $0.25" in markdown
    assert "- Max cost: $0.05" in markdown
    assert "- Budget: blocked" in markdown
    assert "- Remote upload: true" in markdown
    assert "- Provider prompt storage: true" in markdown
    assert "OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD" in markdown
