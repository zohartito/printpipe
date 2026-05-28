"""Action plan helpers for remaining physical validation evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printpipe.beta.physical_status import (
    DEFAULT_REQUIRED_FAMILIES,
    build_physical_validation_status,
)

PROOF_BOUNDARY = (
    "Digital artifacts, generated coupons, and slice receipts do not count as "
    "physical proof until a real print is recorded."
)

_FAMILY_PROFILES = {
    "pla": {
        "material": "Bambu PLA Basic",
        "object_label": "PLA validation coupon",
        "photo": "/path/to/printed-pla-coupon-photo.jpg",
        "required_fields": ("operator", "photo artifact", "first_layer", "adhesion"),
        "flags": (
            ("--first-layer", "clean, continuous first layer; no lifting"),
            ("--adhesion", "held through print and released after cooling"),
        ),
    },
    "petg": {
        "material": "Bambu PETG Basic",
        "object_label": "PETG validation coupon",
        "photo": "/path/to/printed-petg-coupon-photo.jpg",
        "required_fields": (
            "operator",
            "photo artifact",
            "first_layer",
            "adhesion",
            "warping",
            "stringing",
        ),
        "flags": (
            ("--first-layer", "clean first layer; no dragging or gaps"),
            ("--adhesion", "held through print and released after cooling"),
            ("--warping", "no visible corner lift or edge curl"),
            ("--stringing", "none or minor hairs only"),
        ),
    },
    "tpu": {
        "material": "SUNLU TPU 90A",
        "object_label": "TPU validation coupon",
        "photo": "/path/to/printed-tpu-coupon-photo.jpg",
        "required_fields": (
            "operator",
            "photo artifact",
            "filament_drying",
            "layer_bonding",
            "flex_recovery",
        ),
        "flags": (
            ("--filament-drying", "50 C for 4-8 h; external spool or dryer feed"),
            ("--layer-bonding", "no visible layer splits after hand flexing"),
            ("--flex-recovery", "returns close to original shape after 20 flexes"),
        ),
    },
}


def build_physical_validation_plan(
    runs_dir: str | Path,
    *,
    required_families: tuple[str, ...] = DEFAULT_REQUIRED_FAMILIES,
) -> dict[str, Any]:
    """Return next physical validation actions for a runs directory."""

    runs_root = Path(runs_dir).expanduser().resolve()
    status = build_physical_validation_status(
        runs_dir,
        required_families=required_families,
    )
    actions = [
        _action_for_family(family, payload, runs_dir=runs_root)
        for family, payload in status["family_status"].items()
        if payload["status"] != "passed"
    ]
    return {
        "schema_version": 1,
        "runs_dir": str(Path(status["runs_dir"])),
        "overall_status": "passed" if not actions else "action_required",
        "required_families": list(status["required_families"]),
        "proof_boundary": PROOF_BOUNDARY,
        "source_status": status,
        "actions": actions,
        "action_count": len(actions),
    }


def render_physical_validation_plan(plan: dict[str, Any]) -> str:
    """Render a human-readable physical validation plan."""

    lines = [
        "PrintPipe Physical Validation Plan",
        f"runs dir: {plan.get('runs_dir', 'unknown')}",
        f"overall: {plan.get('overall_status', 'unknown')}",
        "",
        str(plan.get("proof_boundary", PROOF_BOUNDARY)),
        "",
        "Actions:",
    ]
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        lines.append("- no physical validation actions required")
        lines.append("")
        return "\n".join(lines)

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        family = str(action.get("family", "unknown")).upper()
        lines.extend(
            [
                f"{index}. {family}: {action.get('status', 'unknown')}",
                f"   reason: {action.get('reason', 'not recorded')}",
                f"   required: {_comma_list(action.get('required_fields'))}",
            ]
        )
        setup_command = str(action.get("setup_command", ""))
        if setup_command:
            lines.append(f"   setup: {setup_command}")
        start_command = str(action.get("start_command", ""))
        if start_command:
            lines.append(f"   start: {start_command}")
        lines.append(f"   command: {action.get('record_command', '')}")
    lines.append("")
    return "\n".join(lines)


def _action_for_family(
    family: str,
    payload: dict[str, Any],
    *,
    runs_dir: Path,
) -> dict[str, Any]:
    profile = _profile_for_family(family)
    best = payload.get("best_evidence")
    best_evidence = best if isinstance(best, dict) else {}
    existing_run_root = str(best_evidence.get("run_root") or "")
    run_root = existing_run_root or str(
        (runs_dir / f"physical-{family}-validation").resolve()
    )
    coupon_paths = _coupon_paths(Path(run_root))
    setup_command = "" if existing_run_root else f"mkdir -p {_quote(run_root)}"
    start_command = (
        ""
        if existing_run_root
        else (
            f"printpipe physical-start --family {family} "
            f"--runs-dir {_quote(str(runs_dir))} --operator {_quote('Zohar')}"
        )
    )
    missing = best_evidence.get("missing_required_evidence")
    required_fields = (
        [str(item) for item in missing]
        if isinstance(missing, list) and missing
        else list(profile["required_fields"])
    )
    return {
        "family": family,
        "status": payload.get("status", "unknown"),
        "reason": payload.get("missing_reason", ""),
        "run_root": run_root,
        "setup_command": setup_command,
        "start_command": start_command,
        "material_hint": profile["material"],
        "object_label": profile["object_label"],
        "print_type": "coupon",
        "required_fields": required_fields,
        "coupon_stl_path": coupon_paths["stl"],
        "coupon_json_path": coupon_paths["json"],
        "record_command": _record_command(family=family, run_root=run_root),
    }


def _record_command(*, family: str, run_root: str) -> str:
    profile = _profile_for_family(family)
    parts = [
        "printpipe",
        "record-physical-evidence",
        _quote(run_root),
        "--material",
        _quote(str(profile["material"])),
        "--printer",
        _quote("Bambu Lab P2S"),
        "--object-label",
        _quote(str(profile["object_label"])),
        "--print-type",
        "coupon",
        "--print-status",
        "passed",
        "--operator",
        _quote("Zohar"),
    ]
    for flag, value in profile["flags"]:
        parts.extend((flag, _quote(value)))
    parts.extend(("--photo", str(profile["photo"])))
    return " ".join(parts)


def _profile_for_family(family: str) -> dict[str, Any]:
    return _FAMILY_PROFILES.get(
        family,
        {
            "material": f"{family.upper()} validation material",
            "object_label": f"{family.upper()} validation coupon",
            "photo": f"/path/to/printed-{family}-coupon-photo.jpg",
            "required_fields": ("operator", "photo artifact"),
            "flags": (),
        },
    )


def _coupon_paths(run_root: Path) -> dict[str, str]:
    geometry_dir = run_root / "40_geometry"
    stl_path = geometry_dir / "physical_validation_coupon_40x15x3.stl"
    json_path = geometry_dir / "physical_validation_coupon_40x15x3.json"
    return {
        "stl": str(stl_path.resolve()) if stl_path.exists() else "",
        "json": str(json_path.resolve()) if json_path.exists() else "",
    }


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _comma_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


__all__ = [
    "PROOF_BOUNDARY",
    "build_physical_validation_plan",
    "render_physical_validation_plan",
]
