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
    return {
        "status": "sliced",
        "family": normalized_family,
        "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        "run_root": str(run_root),
        "bundle_path": str(bundle_path.resolve()),
        "bundle_validation_path": _bundle_validation_path(run_root),
        **payload,
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
    }


def _bundle_validation_path(run_root: Path) -> str:
    path = run_root / "60_bundle" / COUPON_BUNDLE_VALIDATION_NAME
    return str(path.resolve()) if path.exists() else ""


__all__ = [
    "COUPON_BUNDLE_NAME",
    "COUPON_BUNDLE_VALIDATION_NAME",
    "slice_coupon_bundle",
    "slice_physical_validation_coupon",
]
