from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.rule_updates import (
    REQUIRED_RULE_UPDATE_TYPES,
    RULE_UPDATE_STATUSES,
    RULE_UPDATE_TYPES,
    build_rule_update,
    build_rule_update_status,
    render_rule_update_markdown,
    render_rule_update_status,
    write_rule_update_files,
)
from printpipe.cli import main


def test_rule_update_packet_writes_json_markdown_and_status(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "run-flat-bracket"
    run_root.mkdir(parents=True)

    update = build_rule_update(
        run_id="run-flat-bracket",
        rule_type="orientation",
        status="verified",
        summary="Applied selected 45 degree bed-fit rotation before bundling.",
        source="Wave 100 flat-bracket dogfood",
        changed_files=("src/printpipe/pipeline/__init__.py",),
        tests=("tests/test_pipeline_existing_mesh.py::test_existing_mesh_pipeline_applies_bed_fit_rotation_before_bundle",),
        notes=("Preview and bundled mesh now use the same orientation.",),
    )
    result = write_rule_update_files(run_root=run_root, update=update)

    payload = json.loads((run_root / "90_beta" / "rule_update_orientation.json").read_text())
    markdown = (run_root / "90_beta" / "rule_update_orientation.md").read_text()
    status = build_rule_update_status(tmp_path / "runs")

    assert result["json_path"].endswith("90_beta/rule_update_orientation.json")
    assert result["markdown_path"].endswith("90_beta/rule_update_orientation.md")
    assert payload["rule_type"] == "orientation"
    assert payload["status"] == "verified"
    assert payload["changed_files"] == ["src/printpipe/pipeline/__init__.py"]
    assert "## Verification" in markdown
    assert status["packet_count"] == 1
    assert status["rule_type_status"]["orientation"]["status"] == "verified"
    assert status["missing_rule_types"] == ["material", "repair"]
    assert status["overall_status"] == "incomplete"


def test_rule_update_status_passes_after_verified_material_orientation_and_repair(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    for rule_type in REQUIRED_RULE_UPDATE_TYPES:
        run_root = runs_dir / f"run-{rule_type}"
        run_root.mkdir(parents=True)
        write_rule_update_files(
            run_root=run_root,
            update=build_rule_update(
                run_id=run_root.name,
                rule_type=rule_type,
                status="verified",
                summary=f"Verified {rule_type} rule update.",
                source="beta triage",
                changed_files=(f"src/printpipe/{rule_type}.py",),
                tests=(f"tests/test_{rule_type}.py",),
            ),
        )

    status = build_rule_update_status(runs_dir)
    text = render_rule_update_status(status)

    assert status["overall_status"] == "passed"
    assert status["missing_rule_types"] == []
    assert status["verified_rule_types"] == list(REQUIRED_RULE_UPDATE_TYPES)
    assert "overall: passed" in text


def test_rule_update_builders_validate_choices_and_markdown() -> None:
    assert "material" in RULE_UPDATE_TYPES
    assert "verified" in RULE_UPDATE_STATUSES

    update = build_rule_update(
        run_id="run-material",
        rule_type="material",
        status="implemented",
        summary="Raised PETG bed profile rule after slice rejection.",
        source="PETG slice dogfood",
        changed_files=("src/printpipe/materials/petg.py",),
        tests=("tests/test_materials_petg.py",),
    )
    markdown = render_rule_update_markdown(update)

    assert "## Rule Update" in markdown
    assert "- Rule type: material" in markdown
    assert "- Status: implemented" in markdown


def test_cli_record_rule_update_and_status(tmp_path: Path, capsys) -> None:
    run_root = tmp_path / "runs" / "run-repair"
    run_root.mkdir(parents=True)

    exit_code = main(
        [
            "record-rule-update",
            str(run_root),
            "--rule-type",
            "repair",
            "--status",
            "verified",
            "--summary",
            "Allowed intentional open-rim meshes with honest repair receipts.",
            "--source",
            "Wave 100 cup/vase dogfood",
            "--changed-file",
            "src/printpipe/mesh/repair.py",
            "--test",
            "tests/test_mesh_repair.py",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["json_path"].endswith("90_beta/rule_update_repair.json")

    status_code = main(["rule-update-status", "--runs-dir", str(tmp_path / "runs"), "--json"])
    status = json.loads(capsys.readouterr().out)

    assert status_code == 0
    assert status["rule_type_status"]["repair"]["status"] == "verified"
    assert status["missing_rule_types"] == ["material", "orientation"]
