"""Build a macOS drag-install DMG around PrintPipe.app."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from printpipe.packaging.macos_app import build_macos_app_bundle


def build_macos_dmg_package(
    *,
    project_root: str | Path = Path("."),
    output_path: str | Path = Path("dist/PrintPipe.dmg"),
    adhoc_sign: bool = False,
    volume_name: str = "PrintPipe",
) -> dict[str, Any]:
    """Build a drag-install DMG containing PrintPipe.app and /Applications."""

    root = Path(project_root).expanduser().resolve()
    target = Path(output_path).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.suffix.lower() != ".dmg":
        raise ValueError("macOS DMG output must end with .dmg")

    hdiutil = shutil.which("hdiutil")
    if hdiutil is None:
        raise RuntimeError("hdiutil is required to build a macOS DMG")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    with tempfile.TemporaryDirectory(prefix="printpipe-dmg-") as temp_dir:
        staging = Path(temp_dir) / "staging"
        staging.mkdir()
        app_result = build_macos_app_bundle(
            project_root=root,
            app_path=staging / "PrintPipe.app",
            adhoc_sign=adhoc_sign,
        )
        _create_applications_link(staging)
        command = [
            hdiutil,
            "create",
            "-volname",
            volume_name,
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(target),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "hdiutil create failed").strip()
            raise RuntimeError(message)

    return {
        "status": "ok",
        "dmg_path": str(target),
        "volume_name": volume_name,
        "app_name": "PrintPipe.app",
        "contains_app": True,
        "contains_applications_link": True,
        "drag_install": True,
        "signed": bool(app_result["signed"]),
        "signing_identity": app_result.get("signing_identity", ""),
        "notarized": False,
        "bundles_python_runtime": app_result["bundles_python_runtime"],
        "bundles_bambu_studio": app_result["bundles_bambu_studio"],
        "hdiutil_command": " ".join(command),
    }


def _create_applications_link(staging: Path) -> None:
    link = staging / "Applications"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to("/Applications")


__all__ = ["build_macos_dmg_package"]
