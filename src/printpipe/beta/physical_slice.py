"""Slice existing physical-validation coupon bundles."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from printpipe.bambu.slicer import run_bambu_cli_slice_stage, run_slice_command

COUPON_BUNDLE_NAME = "physical_validation_coupon_40x15x3.3mf"
COUPON_BUNDLE_VALIDATION_NAME = "physical_validation_coupon_40x15x3_bundle_validation.json"


def slice_physical_validation_coupon(
    runs_dir: str | Path,
    *,
    family: str,
    executable: str | Path | None = None,
    slice_runner: Any | None = None,
) -> dict[str, Any]:
    """Run the Bambu CLI slice gate for an existing validation coupon bundle."""

    normalized_family = family.strip().lower()
    if not normalized_family:
        raise ValueError("family must not be blank")

    run_root = Path(runs_dir).expanduser().resolve() / f"physical-{normalized_family}-validation"
    bundle_path = run_root / "60_bundle" / COUPON_BUNDLE_NAME
    if not bundle_path.exists():
        raise FileNotFoundError(
            "physical validation coupon bundle was not found; run "
            f"`printpipe physical-start --family {normalized_family}` first"
        )

    payload = slice_coupon_bundle(
        run_root=run_root,
        bundle_path=bundle_path,
        executable=executable,
        slice_runner=slice_runner,
    )
    handoff_payload = refresh_handoff_slice_receipt(
        run_root=run_root,
        slice_payload=payload,
    )
    return {
        "status": "sliced" if payload["slice_status"] == "succeeded" else "failed",
        "family": normalized_family,
        "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        "run_root": str(run_root),
        "bundle_path": str(bundle_path.resolve()),
        "bundle_validation_path": _bundle_validation_path(run_root),
        **payload,
        **handoff_payload,
    }


def slice_coupon_bundle(
    *,
    run_root: Path,
    bundle_path: Path,
    executable: str | Path | None,
    slice_runner: Any | None,
) -> dict[str, Any]:
    """Slice a coupon bundle and return stable receipt metadata."""

    runner = run_slice_command if slice_runner is None else slice_runner
    layout = SimpleNamespace(slice_dir=run_root / "70_slice")
    receipt = run_bambu_cli_slice_stage(
        three_mf_path=bundle_path,
        run_layout=layout,
        executable=executable,
        slice_runner=runner,
    )
    result_path = ""
    for artifact in receipt.artifacts:
        if artifact.path.name == "slice_result.json":
            result_path = str(artifact.path.resolve())
            break
    return {
        "slice_requested": True,
        "slice_status": receipt.status.value,
        "slice_message": receipt.message,
        "slice_result_path": result_path,
        "slice_time_seconds": receipt.metrics.get("time_seconds"),
        "slice_filament_g": receipt.metrics.get("filament_g"),
        "slice_layer_count": receipt.metrics.get("layer_count"),
        "slice_cost": receipt.metrics.get("cost"),
    }


def _bundle_validation_path(run_root: Path) -> str:
    path = run_root / "60_bundle" / COUPON_BUNDLE_VALIDATION_NAME
    return str(path.resolve()) if path.exists() else ""


def refresh_handoff_slice_receipt(
    *,
    run_root: Path,
    slice_payload: dict[str, Any],
) -> dict[str, Any]:
    """Refresh only the slice section in the physical print handoff."""

    handoff_path = run_root / "90_physical" / "physical_print_handoff.md"
    if not handoff_path.exists():
        return {
            "handoff_markdown_path": "",
            "handoff_updated": False,
        }

    original = handoff_path.read_text(encoding="utf-8")
    updated = _replace_or_insert_slice_section(original, _slice_section(slice_payload))
    changed = updated != original
    if changed:
        handoff_path.write_text(updated, encoding="utf-8")
    return {
        "handoff_markdown_path": str(handoff_path.resolve()),
        "handoff_updated": changed,
    }


def _slice_section(slice_payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "## Slice Receipt",
            f"- Requested: {slice_payload.get('slice_requested', False)}",
            f"- Status: {slice_payload.get('slice_status', 'not_requested')}",
            f"- Message: {slice_payload.get('slice_message', '')}",
            _estimate_line(slice_payload),
            f"- Result JSON: {slice_payload.get('slice_result_path') or 'not generated'}",
            "",
        ]
    )


def _replace_or_insert_slice_section(text: str, section: str) -> str:
    lines = text.splitlines()
    slice_start = _heading_index(lines, "## Slice Receipt")
    if slice_start is not None:
        slice_end = _next_heading_index(lines, slice_start + 1)
        replacement = _section_lines(section)
        updated = lines[:slice_start] + replacement + lines[slice_end:]
        return "\n".join(updated).rstrip() + "\n"

    validate_start = _heading_index(lines, "## Validate During The Print")
    insertion = _section_lines(section)
    if validate_start is not None:
        updated = lines[:validate_start] + insertion + lines[validate_start:]
        return "\n".join(updated).rstrip() + "\n"

    return text.rstrip() + "\n\n" + section


def _section_lines(section: str) -> list[str]:
    return section.rstrip("\n").splitlines() + [""]


def _estimate_line(slice_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    time_seconds = slice_payload.get("slice_time_seconds")
    if isinstance(time_seconds, int):
        parts.append(_format_duration(time_seconds))

    filament_g = slice_payload.get("slice_filament_g")
    if isinstance(filament_g, int | float):
        parts.append(f"{float(filament_g):.2f} g")

    layer_count = slice_payload.get("slice_layer_count")
    if isinstance(layer_count, int):
        parts.append(f"{layer_count} layers")

    cost = slice_payload.get("slice_cost")
    if isinstance(cost, int | float):
        parts.append(f"${float(cost):.2f}")

    if not parts:
        return "- Estimate: not recorded"
    return "- Estimate: " + " / ".join(parts)


def _format_duration(seconds: int) -> str:
    remaining = max(seconds, 0)
    hours, remaining = divmod(remaining, 3600)
    minutes, seconds = divmod(remaining, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def _heading_index(lines: list[str], heading: str) -> int | None:
    for index, line in enumerate(lines):
        if line == heading:
            return index
    return None


def _next_heading_index(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            return index
    return len(lines)


__all__ = [
    "COUPON_BUNDLE_NAME",
    "COUPON_BUNDLE_VALIDATION_NAME",
    "refresh_handoff_slice_receipt",
    "slice_coupon_bundle",
    "slice_physical_validation_coupon",
]
