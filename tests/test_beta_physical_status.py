from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_status import (
    build_physical_validation_status,
    render_physical_validation_status,
)
from printpipe.cli import main


def test_physical_validation_status_requires_passed_packet_per_material_family(
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
        runs_dir / "run-tpu-fail",
        material="SUNLU TPU 90A",
        print_status="failed",
        filament_drying="50 C for 6 h",
        layer_bonding="split at layer 12",
        flex_recovery="not tested because print failed",
    )

    status = build_physical_validation_status(runs_dir)

    assert status["overall_status"] == "missing_passed_evidence"
    assert status["required_families"] == ["pla", "petg", "tpu"]
    assert status["family_status"]["pla"]["status"] == "passed"
    assert status["family_status"]["pla"]["passed_count"] == 1
    assert status["family_status"]["pla"]["best_evidence"]["run_id"] == "run-pla-pass"
    assert status["family_status"]["petg"]["status"] == "missing"
    assert status["family_status"]["petg"]["missing_reason"] == "no physical evidence packet found"
    assert status["family_status"]["tpu"]["status"] == "recorded_but_not_passed"
    assert status["family_status"]["tpu"]["packet_count"] == 1
    assert status["family_status"]["tpu"]["best_evidence"]["print_status"] == "failed"


def test_physical_validation_status_marks_passed_packet_with_missing_fields_incomplete(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_evidence(
        runs_dir / "run-petg-incomplete",
        material="Bambu PETG-CF",
        print_status="passed",
        first_layer="clean first layer",
    )

    status = build_physical_validation_status(runs_dir, required_families=("petg",))

    assert status["overall_status"] == "missing_passed_evidence"
    assert status["family_status"]["petg"]["status"] == "incomplete"
    assert status["family_status"]["petg"]["best_evidence"]["missing_required_evidence"] == [
        "adhesion",
        "warping",
        "stringing",
    ]


def test_render_physical_validation_status_summarizes_remaining_materials(
    tmp_path: Path,
) -> None:
    status = build_physical_validation_status(tmp_path / "runs")

    text = render_physical_validation_status(status)

    assert "PrintPipe Physical Validation" in text
    assert "overall: missing_passed_evidence" in text
    assert "pla: missing" in text
    assert "petg: missing" in text
    assert "tpu: missing" in text


def test_cli_physical_status_prints_json_and_can_gate_strictly(
    tmp_path: Path,
    capsys,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_evidence(
        runs_dir / "run-pla-pass",
        material="Bambu PLA Basic",
        print_status="passed",
        first_layer="clean first layer",
        adhesion="held through print",
    )

    exit_code = main(["physical-status", "--runs-dir", str(runs_dir), "--json", "--strict"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert payload["overall_status"] == "missing_passed_evidence"
    assert payload["family_status"]["pla"]["status"] == "passed"
    assert payload["family_status"]["petg"]["status"] == "missing"
    assert payload["family_status"]["tpu"]["status"] == "missing"


def _write_evidence(
    run_root: Path,
    *,
    material: str,
    print_status: str,
    first_layer: str = "",
    adhesion: str = "",
    warping: str = "",
    stringing: str = "",
    filament_drying: str = "",
    layer_bonding: str = "",
    flex_recovery: str = "",
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
        filament_drying=filament_drying,
        layer_bonding=layer_bonding,
        flex_recovery=flex_recovery,
        artifacts=(PhysicalArtifact(label="Coupon photo", path=photo, kind="photo"),),
    )
    write_physical_evidence_files(
        run_root=run_root,
        evidence=evidence,
        copy_artifacts=True,
    )
