"""Starter packets for physical validation prints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printpipe.beta.physical import (
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_plan import PROOF_BOUNDARY, build_physical_validation_plan


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
    return {
        "status": "started",
        "family": normalized_family,
        "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        "operator": operator,
        "run_root": str(run_root),
        "json_path": written["json_path"],
        "markdown_path": written["markdown_path"],
        "missing_required_evidence": written["missing_required_evidence"],
        "record_command": action["record_command"],
    }


__all__ = ["start_physical_validation"]
