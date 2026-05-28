from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_plan import (
    build_physical_validation_plan,
    render_physical_validation_plan,
)
from printpipe.beta.physical_slice import slice_physical_validation_coupon
from printpipe.beta.physical_start import start_physical_validation
from printpipe.beta.physical_status import build_physical_validation_status
from printpipe.bambu.slicer import SliceResult
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
    assert tpu_action["start_command"] == (
        f'printpipe physical-start --family tpu --runs-dir "{runs_dir.resolve()}" '
        '--operator "Zohar"'
    )
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
    assert petg_action["start_command"] == ""
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
    assert "start: printpipe physical-start" in text
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
    assert "physical-start" in payload["actions"][0]["start_command"]
    assert "record-physical-evidence" in payload["actions"][0]["record_command"]


def test_physical_validation_plan_surfaces_started_coupon_artifacts(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )

    plan = build_physical_validation_plan(runs_dir)

    pla_action = plan["actions"][0]
    run_root = (runs_dir / "physical-pla-validation").resolve()
    coupon_sidecar = json.loads(
        Path(pla_action["coupon_json_path"]).read_text(encoding="utf-8")
    )
    assert pla_action["family"] == "pla"
    assert pla_action["status"] == "recorded_but_not_passed"
    assert pla_action["detail"] == (
        "Print the coupon from the STL, take a real photo, then run the "
        "record command with real observations."
    )
    assert pla_action["command"] == f'printpipe open-folder "{run_root}" --target run'
    assert pla_action["command_kind"] == "print_handoff_command"
    assert pla_action["coupon_stl_path"].endswith(
        "40_geometry/physical_validation_coupon_40x15x3.stl"
    )
    assert pla_action["coupon_json_path"].endswith(
        "40_geometry/physical_validation_coupon_40x15x3.json"
    )
    assert pla_action["bundle_path"].endswith(
        "60_bundle/physical_validation_coupon_40x15x3.3mf"
    )
    assert pla_action["bundle_validation_path"].endswith(
        "60_bundle/physical_validation_coupon_40x15x3_bundle_validation.json"
    )
    assert pla_action["slice_command"] == (
        f'printpipe physical-slice --family pla --runs-dir "{runs_dir.resolve()}"'
    )
    assert pla_action["slice_result_path"] == ""
    assert pla_action["handoff_markdown_path"].endswith(
        "90_physical/physical_print_handoff.md"
    )
    assert "first layer continuity" in coupon_sidecar["print_validation"]
    assert "flex recovery" not in coupon_sidecar["print_validation"]
    assert "handoff: " in render_physical_validation_plan(plan)
    assert "bundle: " in render_physical_validation_plan(plan)
    assert "slice: printpipe physical-slice" in render_physical_validation_plan(plan)
    assert "next: printpipe open-folder" in render_physical_validation_plan(plan)


def test_start_physical_validation_writes_not_printed_starter_packet(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"

    result = start_physical_validation(
        runs_dir,
        family="tpu",
        operator="Zohar",
    )

    run_root = runs_dir / "physical-tpu-validation"
    evidence_path = run_root / "90_physical" / "physical_evidence.json"
    handoff_path = run_root / "90_physical" / "physical_print_handoff.md"
    coupon_path = run_root / "40_geometry" / "physical_validation_coupon_40x15x3.stl"
    coupon_sidecar_path = (
        run_root / "40_geometry" / "physical_validation_coupon_40x15x3.json"
    )
    bundle_path = run_root / "60_bundle" / "physical_validation_coupon_40x15x3.3mf"
    bundle_validation_path = (
        run_root / "60_bundle" / "physical_validation_coupon_40x15x3_bundle_validation.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    coupon_sidecar = json.loads(coupon_sidecar_path.read_text(encoding="utf-8"))
    bundle_validation = json.loads(bundle_validation_path.read_text(encoding="utf-8"))
    status = build_physical_validation_status(runs_dir, required_families=("tpu",))

    assert result["status"] == "started"
    assert result["family"] == "tpu"
    assert result["run_root"] == str(run_root.resolve())
    assert result["json_path"] == str(evidence_path.resolve())
    assert result["handoff_markdown_path"] == str(handoff_path.resolve())
    assert result["coupon_stl_path"] == str(coupon_path.resolve())
    assert result["coupon_json_path"] == str(coupon_sidecar_path.resolve())
    assert result["bundle_path"] == str(bundle_path.resolve())
    assert result["bundle_validation_path"] == str(bundle_validation_path.resolve())
    assert result["slice_requested"] is False
    assert result["slice_status"] == "not_requested"
    assert result["slice_result_path"] == ""
    assert coupon_path.exists()
    assert bundle_path.exists()
    assert bundle_validation["ok"] is True
    assert bundle_validation["bundle_path"] == str(bundle_path.resolve())
    assert coupon_sidecar["material"] == "SUNLU TPU 90A"
    assert coupon_sidecar["use_case"] == "TPU physical validation"
    assert "flex recovery" in coupon_sidecar["print_validation"]
    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert "PrintPipe Physical Validation Print Handoff" in handoff_text
    assert str(coupon_path.resolve()) in handoff_text
    assert str(bundle_path.resolve()) in handoff_text
    assert "flex recovery" in handoff_text
    assert "Digital artifacts, generated coupons, and slice receipts" in handoff_text
    assert result["record_command"] in handoff_text
    assert result["record_command"].startswith(
        f'printpipe record-physical-evidence "{run_root.resolve()}"'
    )
    assert evidence["material"] == "SUNLU TPU 90A"
    assert evidence["object_label"] == "TPU validation coupon"
    assert evidence["print_status"] == "not_printed"
    assert evidence["operator"] == "Zohar"
    assert "Starter packet" in "\n".join(evidence["notes"])
    assert status["overall_status"] == "missing_passed_evidence"
    assert status["family_status"]["tpu"]["status"] == "recorded_but_not_passed"


def test_cli_physical_start_prints_json_and_does_not_pass_gate(
    tmp_path: Path,
    capsys,
) -> None:
    runs_dir = tmp_path / "runs"

    exit_code = main(
        [
            "physical-start",
            "--family",
            "pla",
            "--runs-dir",
            str(runs_dir),
            "--operator",
            "Zohar",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    status = build_physical_validation_status(runs_dir, required_families=("pla",))

    assert exit_code == 0
    assert payload["status"] == "started"
    assert payload["family"] == "pla"
    assert payload["json_path"].endswith("90_physical/physical_evidence.json")
    assert payload["handoff_markdown_path"].endswith(
        "90_physical/physical_print_handoff.md"
    )
    assert payload["coupon_stl_path"].endswith(
        "40_geometry/physical_validation_coupon_40x15x3.stl"
    )
    assert payload["coupon_json_path"].endswith(
        "40_geometry/physical_validation_coupon_40x15x3.json"
    )
    assert payload["bundle_path"].endswith(
        "60_bundle/physical_validation_coupon_40x15x3.3mf"
    )
    assert payload["bundle_validation_path"].endswith(
        "60_bundle/physical_validation_coupon_40x15x3_bundle_validation.json"
    )
    assert payload["slice_requested"] is False
    assert payload["slice_status"] == "not_requested"
    assert "record-physical-evidence" in payload["record_command"]
    assert status["family_status"]["pla"]["status"] == "recorded_but_not_passed"


def test_cli_physical_start_text_prints_coupon_and_handoff_paths(
    tmp_path: Path,
    capsys,
) -> None:
    runs_dir = tmp_path / "runs"

    exit_code = main(
        [
            "physical-start",
            "--family",
            "petg",
            "--runs-dir",
            str(runs_dir),
            "--operator",
            "Zohar",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "coupon stl:" in captured.out
    assert "physical_validation_coupon_40x15x3.stl" in captured.out
    assert "bundle 3mf:" in captured.out
    assert "physical_validation_coupon_40x15x3.3mf" in captured.out
    assert "print handoff:" in captured.out
    assert "physical_print_handoff.md" in captured.out


def test_physical_start_can_slice_coupon_bundle_with_explicit_runner(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    calls: list[tuple[tuple[str | Path, ...], object]] = []

    def fake_slice_runner(command, run_layout):
        calls.append((tuple(command), run_layout))
        return SliceResult(return_code=0, time_seconds=300, filament_g=1.25, layer_count=15)

    result = start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
        run_slice=True,
        slice_executable=tmp_path / "BambuStudio",
        slice_runner=fake_slice_runner,
    )

    slice_result_path = runs_dir / "physical-pla-validation" / "70_slice" / "slice_result.json"
    payload = json.loads(slice_result_path.read_text(encoding="utf-8"))
    plan = build_physical_validation_plan(runs_dir)

    assert result["slice_requested"] is True
    assert result["slice_status"] == "succeeded"
    assert result["slice_message"] == "Bambu CLI slice passed."
    assert result["slice_result_path"] == str(slice_result_path.resolve())
    assert payload["time_seconds"] == 300
    assert calls[0][0][0] == str(tmp_path / "BambuStudio")
    assert calls[0][0][-1].endswith("physical_validation_coupon_40x15x3.3mf")
    assert plan["actions"][0]["slice_result_path"] == str(slice_result_path.resolve())


def test_physical_slice_slices_existing_coupon_without_rewriting_evidence(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="petg",
        operator="Zohar",
    )
    evidence_path = (
        runs_dir / "physical-petg-validation" / "90_physical" / "physical_evidence.json"
    )
    handoff_path = (
        runs_dir / "physical-petg-validation" / "90_physical" / "physical_print_handoff.md"
    )
    evidence_before = evidence_path.read_text(encoding="utf-8")
    handoff_before = handoff_path.read_text(encoding="utf-8")
    calls: list[tuple[tuple[str | Path, ...], object]] = []

    def fake_slice_runner(command, run_layout):
        calls.append((tuple(command), run_layout))
        return SliceResult(return_code=0, time_seconds=240, filament_g=1.4, layer_count=15)

    result = slice_physical_validation_coupon(
        runs_dir,
        family="petg",
        executable=tmp_path / "BambuStudio",
        slice_runner=fake_slice_runner,
    )
    plan = build_physical_validation_plan(runs_dir)
    petg_action = next(action for action in plan["actions"] if action["family"] == "petg")
    rendered = render_physical_validation_plan(plan)

    assert result["status"] == "sliced"
    assert result["family"] == "petg"
    assert result["slice_status"] == "succeeded"
    assert result["slice_message"] == "Bambu CLI slice passed."
    assert result["slice_result_path"].endswith("70_slice/slice_result.json")
    assert result["handoff_markdown_path"] == str(handoff_path.resolve())
    assert result["handoff_updated"] is True
    assert calls[0][0][0] == str(tmp_path / "BambuStudio")
    assert calls[0][0][-1].endswith("physical_validation_coupon_40x15x3.3mf")
    assert evidence_path.read_text(encoding="utf-8") == evidence_before
    handoff_after = handoff_path.read_text(encoding="utf-8")
    assert handoff_after != handoff_before
    assert "## Slice Receipt" in handoff_after
    assert "- Status: succeeded" in handoff_after
    assert f"- Result JSON: {result['slice_result_path']}" in handoff_after
    assert petg_action["slice_result_path"] == result["slice_result_path"]
    assert petg_action["slice_command"] == ""
    assert f"slice receipt: {result['slice_result_path']}" in rendered


def test_cli_physical_start_rejects_bambu_cli_without_slice(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "physical-start",
                "--family",
                "pla",
                "--runs-dir",
                str(tmp_path / "runs"),
                "--bambu-cli",
                str(tmp_path / "BambuStudio"),
            ]
        )


def test_cli_physical_slice_slices_existing_coupon(
    tmp_path: Path,
    capsys,
) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )
    fake_bambu = tmp_path / "fake_bambu.py"
    fake_bambu.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import pathlib",
                "import sys",
                "output_dir = pathlib.Path(sys.argv[sys.argv.index('--outputdir') + 1])",
                "output_dir.mkdir(parents=True, exist_ok=True)",
                "gcode = output_dir / 'plate_1.gcode'",
                "gcode.write_text('; estimated printing time (normal mode) = 4m 0s\\n"
                "; total filament weight [g] = 1.40\\n"
                "; total layer number = 15\\n')",
                "print(f'Exported G-code: {gcode}')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_bambu.chmod(0o755)

    exit_code = main(
        [
            "physical-slice",
            "--family",
            "pla",
            "--runs-dir",
            str(runs_dir),
            "--bambu-cli",
            str(fake_bambu),
        ]
    )

    captured = capsys.readouterr()
    result_path = runs_dir / "physical-pla-validation" / "70_slice" / "slice_result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "slice status: succeeded" in captured.out
    assert str(result_path.resolve()) in captured.out
    assert "print handoff:" in captured.out
    assert payload["time_seconds"] == 240
    assert payload["filament_g"] == 1.4
    assert payload["cost"] is None


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
