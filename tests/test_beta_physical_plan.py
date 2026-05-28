from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_plan import (
    build_physical_validation_plan,
    render_physical_validation_plan,
)
from printpipe.cli import main


def test_physical_validation_plan_turns_missing_families_into_actions(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"

    plan = build_physical_validation_plan(runs_dir)

    assert plan["overall_status"] == "action_required"
    assert plan["action_count"] == 3
    assert plan["proof_boundary"] == (
        "Digital artifacts, generated coupons, and slice receipts do not count as "
        "physical proof until a real print is recorded."
    )
    families = [action["family"] for action in plan["actions"]]
    assert families == ["pla", "petg", "tpu"]
    tpu_action = plan["actions"][2]
    assert tpu_action["required_fields"] == [
        "operator",
        "photo artifact",
        "filament_drying",
        "layer_bonding",
        "flex_recovery",
    ]
    tpu_run_root = (runs_dir / "physical-tpu-validation").resolve()
    assert tpu_action["run_root"] == str(tpu_run_root)
    assert tpu_action["setup_command"] == f'mkdir -p "{tpu_run_root}"'
    assert tpu_action["record_command"] == (
        f'printpipe record-physical-evidence "{tpu_run_root}" '
        '--material "SUNLU TPU 90A" --printer "Bambu Lab P2S" '
        '--object-label "TPU validation coupon" --print-type coupon '
        '--print-status passed --operator "Zohar" '
        '--filament-drying "50 C for 4-8 h; external spool or dryer feed" '
        '--layer-bonding "no visible layer splits after hand flexing" '
        '--flex-recovery "returns close to original shape after 20 flexes" '
        '--photo /path/to/printed-tpu-coupon-photo.jpg'
    )


def test_physical_validation_plan_omits_passed_family_and_targets_incomplete_packet(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_evidence(
        runs_dir / "run-pla-pass",
        material="Bambu PLA Basic",
        print_status="passed",
        first_layer="clean first layer",
        adhesion="held through print",
    )
    _write_evidence(
        runs_dir / "run-petg-incomplete",
        material="Bambu PETG-CF",
        print_status="passed",
        first_layer="clean first layer",
    )

    plan = build_physical_validation_plan(runs_dir)

    assert [action["family"] for action in plan["actions"]] == ["petg", "tpu"]
    petg_action = plan["actions"][0]
    assert petg_action["status"] == "incomplete"
    assert petg_action["run_root"] == str((runs_dir / "run-petg-incomplete").resolve())
    assert petg_action["setup_command"] == ""
    assert petg_action["required_fields"] == ["adhesion", "warping", "stringing"]
    assert f'"{(runs_dir / "run-petg-incomplete").resolve()}"' in petg_action["record_command"]
    assert "--warping" in petg_action["record_command"]
    assert "--stringing" in petg_action["record_command"]


def test_render_physical_validation_plan_includes_commands_and_proof_boundary(
    tmp_path: Path,
) -> None:
    plan = build_physical_validation_plan(tmp_path / "runs")

    text = render_physical_validation_plan(plan)

    assert "PrintPipe Physical Validation Plan" in text
    assert "overall: action_required" in text
    assert "Digital artifacts, generated coupons, and slice receipts do not count" in text
    assert "1. PLA: missing" in text
    assert "setup: mkdir -p" in text
    assert "printpipe record-physical-evidence" in text
    assert "--first-layer" in text
    assert "--photo /path/to/printed-pla-coupon-photo.jpg" in text


def test_cli_physical_plan_prints_json(
    tmp_path: Path,
    capsys,
) -> None:
    runs_dir = tmp_path / "runs"

    exit_code = main(["physical-plan", "--runs-dir", str(runs_dir), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["overall_status"] == "action_required"
    assert payload["actions"][0]["family"] == "pla"
    assert "record-physical-evidence" in payload["actions"][0]["record_command"]


def _write_evidence(
    run_root: Path,
    *,
    material: str,
    print_status: str,
    first_layer: str = "",
    adhesion: str = "",
    warping: str = "",
    stringing: str = "",
) -> None:
    run_root.mkdir(parents=True)
    photo = run_root / "coupon.jpg"
    photo.write_bytes(b"photo")
    evidence = build_physical_print_evidence(
        run_id=run_root.name,
        material=material,
        printer="Bambu Lab P2S",
        object_label="validation coupon",
        print_type="coupon",
        print_status=print_status,
        operator="Zohar",
        first_layer=first_layer,
        adhesion=adhesion,
        warping=warping,
        stringing=stringing,
        artifacts=(PhysicalArtifact(label="Coupon photo", path=photo, kind="photo"),),
    )
    write_physical_evidence_files(
        run_root=run_root,
        evidence=evidence,
        copy_artifacts=True,
    )
