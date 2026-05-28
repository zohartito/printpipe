"""Starter packets for physical validation prints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printpipe.calibration.flex_coupon import write_flex_coupon_artifacts
from printpipe.beta.physical import (
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_plan import PROOF_BOUNDARY, build_physical_validation_plan

_VALIDATION_POINTS = {
    "pla": (
        "bed adhesion",
        "first layer continuity",
        "dimension check",
        "release after cooling",
    ),
    "petg": (
        "bed adhesion",
        "first layer continuity",
        "warping check",
        "stringing check",
    ),
    "tpu": (
        "bed adhesion",
        "flex recovery",
        "interlayer bonding",
        "support/brim removability",
    ),
}


def start_physical_validation(
    runs_dir: str | Path,
    *,
    family: str,
    operator: str = "",
) -> dict[str, Any]:
    """Create a starter packet for a material-family validation print."""

    normalized_family = family.strip().lower()
    if not normalized_family:
        raise ValueError("family must not be blank")

    plan = build_physical_validation_plan(
        runs_dir,
        required_families=(normalized_family,),
    )
    if not plan["actions"]:
        return {
            "status": "already_passed",
            "family": normalized_family,
            "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        }

    action = plan["actions"][0]
    run_root = Path(str(action["run_root"])).expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    coupon_receipt = write_flex_coupon_artifacts(
        run_root / "40_geometry",
        material=str(action["material_hint"]),
        use_case=f"{normalized_family.upper()} physical validation",
        print_validation_points=_validation_points(normalized_family),
        stem="physical_validation_coupon_40x15x3",
    )
    coupon_paths = {
        "stl": _artifact_path(coupon_receipt, suffix=".stl"),
        "json": _artifact_path(coupon_receipt, suffix=".json"),
    }
    evidence = build_physical_print_evidence(
        run_id=run_root.name,
        material=str(action["material_hint"]),
        printer="Bambu Lab P2S",
        object_label=str(action["object_label"]),
        print_type=str(action["print_type"]),
        print_status="not_printed",
        operator=operator,
        notes=(
            "Starter packet created before physical print; this is not passed evidence.",
            PROOF_BOUNDARY,
            "After printing, rerun the record command with real observations and a photo path.",
        ),
    )
    written = write_physical_evidence_files(run_root=run_root, evidence=evidence)
    handoff_path = _write_handoff_markdown(
        run_root=run_root,
        family=normalized_family,
        action=action,
        coupon_paths=coupon_paths,
        validation_points=_validation_points(normalized_family),
    )
    return {
        "status": "started",
        "family": normalized_family,
        "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        "operator": operator,
        "run_root": str(run_root),
        "json_path": written["json_path"],
        "markdown_path": written["markdown_path"],
        "missing_required_evidence": written["missing_required_evidence"],
        "coupon_stl_path": coupon_paths["stl"],
        "coupon_json_path": coupon_paths["json"],
        "handoff_markdown_path": str(handoff_path),
        "record_command": action["record_command"],
    }


def _artifact_path(receipt: Any, *, suffix: str) -> str:
    for artifact in getattr(receipt, "artifacts", ()):
        path = Path(artifact.path)
        if path.suffix == suffix:
            return str(path.resolve())
    return ""


def _validation_points(family: str) -> tuple[str, ...]:
    return _VALIDATION_POINTS.get(
        family,
        (
            "bed adhesion",
            "first layer continuity",
            "dimension check",
        ),
    )


def _write_handoff_markdown(
    *,
    run_root: Path,
    family: str,
    action: dict[str, Any],
    coupon_paths: dict[str, str],
    validation_points: tuple[str, ...],
) -> Path:
    handoff_path = run_root / "90_physical" / "physical_print_handoff.md"
    record_command = str(action.get("record_command", ""))
    material = str(action.get("material_hint", "unknown"))
    object_label = str(action.get("object_label", "validation coupon"))
    validation_lines = "\n".join(f"- {point}" for point in validation_points)
    handoff_path.write_text(
        "\n".join(
            [
                "# PrintPipe Physical Validation Print Handoff",
                "",
                "## Run Context",
                f"- Family: {family.upper()}",
                f"- Material: {material}",
                f"- Object: {object_label}",
                f"- Run folder: {run_root}",
                "",
                "## Printable Coupon",
                f"- STL: {coupon_paths.get('stl') or 'not generated'}",
                f"- JSON sidecar: {coupon_paths.get('json') or 'not generated'}",
                "",
                "## Validate During The Print",
                validation_lines,
                "",
                "## Record Evidence After Printing",
                "Replace the placeholder photo path with the real coupon photo path, then run:",
                "",
                "```bash",
                record_command,
                "```",
                "",
                "## Proof Boundary",
                PROOF_BOUNDARY,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return handoff_path.resolve()


__all__ = ["start_physical_validation"]
