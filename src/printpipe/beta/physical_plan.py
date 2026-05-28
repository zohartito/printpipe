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
        detail = str(action.get("detail", ""))
        if detail:
            lines.append(f"   detail: {detail}")
        setup_command = str(action.get("setup_command", ""))
        if setup_command:
            lines.append(f"   setup: {setup_command}")
        start_command = str(action.get("start_command", ""))
        if start_command:
            lines.append(f"   start: {start_command}")
        command = str(action.get("command", ""))
        if command:
            lines.append(f"   next: {command}")
        handoff_path = str(action.get("handoff_markdown_path", ""))
        if handoff_path:
            lines.append(f"   handoff: {handoff_path}")
        bundle_path = str(action.get("bundle_path", ""))
        if bundle_path:
            lines.append(f"   bundle: {bundle_path}")
        slice_result_path = str(action.get("slice_result_path", ""))
        if slice_result_path:
            lines.append(f"   slice receipt: {slice_result_path}")
        else:
            slice_command = str(action.get("slice_command", ""))
            if slice_command:
                lines.append(f"   slice: {slice_command}")
        lines.append(f"   record after print: {action.get('record_command', '')}")
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
    bundle_paths = _bundle_paths(Path(run_root))
    slice_path = _slice_result_path(Path(run_root))
    slice_command = _slice_command(
        family=family,
        runs_dir=runs_dir,
        has_bundle=bool(bundle_paths["bundle"]),
        has_slice=bool(slice_path),
    )
    setup_command = "" if existing_run_root else f"mkdir -p {_quote(run_root)}"
    start_command = (
        ""
        if existing_run_root
        else (
            f"printpipe physical-start --family {family} "
            f"--runs-dir {_quote(str(runs_dir))} --operator {_quote('Zohar')}"
        )
    )
    print_status = str(best_evidence.get("print_status") or "")
    missing = best_evidence.get("missing_required_evidence")
    required_fields = (
        [str(item) for item in missing]
        if isinstance(missing, list) and missing
        else list(profile["required_fields"])
    )
    action = {
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
        "bundle_path": bundle_paths["bundle"],
        "bundle_validation_path": bundle_paths["validation"],
        "slice_command": slice_command,
        "slice_result_path": slice_path,
        "handoff_markdown_path": _handoff_path(Path(run_root)),
        "record_command": _record_command(family=family, run_root=run_root),
    }
    action["detail"] = _action_detail(
        status=str(payload.get("status") or ""),
        print_status=print_status,
    )
    command = _next_command_for_action(
        status=str(payload.get("status") or ""),
        print_status=print_status,
        run_root=run_root,
    )
    if command:
        action["command"] = command
        action["command_kind"] = "print_handoff_command"
    return action


def _action_detail(*, status: str, print_status: str) -> str:
    if status == "missing":
        return "Create the starter packet and coupon artifacts before claiming any print evidence."
    if status == "incomplete":
        return "Complete the physical evidence packet with the missing required fields and an existing photo artifact."
    if status == "recorded_but_not_passed" and print_status == "not_printed":
        return "Print the coupon from the STL, take a real photo, then run the record command with real observations."
    if status == "recorded_but_not_passed":
        return "Reprint or record a new passed evidence packet with real observations and a photo artifact."
    return "Physical validation evidence is still required before this family can pass."


def _next_command_for_action(*, status: str, print_status: str, run_root: str) -> str:
    if status == "recorded_but_not_passed" and print_status == "not_printed":
        return f"printpipe open-folder {_quote(run_root)} --target run"
    return ""


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
        _quote("<passed|failed|partial>"),
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


def _bundle_paths(run_root: Path) -> dict[str, str]:
    bundle_dir = run_root / "60_bundle"
    bundle_path = bundle_dir / "physical_validation_coupon_40x15x3.3mf"
    validation_path = bundle_dir / "physical_validation_coupon_40x15x3_bundle_validation.json"
    return {
        "bundle": str(bundle_path.resolve()) if bundle_path.exists() else "",
        "validation": str(validation_path.resolve()) if validation_path.exists() else "",
    }


def _slice_result_path(run_root: Path) -> str:
    path = run_root / "70_slice" / "slice_result.json"
    return str(path.resolve()) if path.exists() else ""


def _slice_command(*, family: str, runs_dir: Path, has_bundle: bool, has_slice: bool) -> str:
    if not has_bundle or has_slice:
        return ""
    return f"printpipe physical-slice --family {family} --runs-dir {_quote(str(runs_dir))}"


def _handoff_path(run_root: Path) -> str:
    path = run_root / "90_physical" / "physical_print_handoff.md"
    return str(path.resolve()) if path.exists() else ""


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
