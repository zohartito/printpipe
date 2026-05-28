"""Build an unsigned macOS .app wrapper around the PrintPipe zipapp."""

from __future__ import annotations

import plistlib
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.packaging.zipapp import build_zipapp_package


def build_macos_app_bundle(
    *,
    project_root: str | Path = Path("."),
    app_path: str | Path = Path("dist/PrintPipe.app"),
    adhoc_sign: bool = False,
) -> dict[str, Any]:
    """Build an unsigned `.app` bundle that runs the portable zipapp."""

    root = Path(project_root).expanduser().resolve()
    target = Path(app_path).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.suffix != ".app":
        raise ValueError("macOS app bundle output must end with .app")

    if target.exists():
        if not target.is_dir():
            raise ValueError(f"macOS app output exists and is not a directory: {target}")
        shutil.rmtree(target)

    contents_dir = target / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    zipapp_result = build_zipapp_package(
        project_root=root,
        output_path=resources_dir / "printpipe.pyz",
    )
    executable = macos_dir / "printpipe"
    executable.write_text(_launcher_script(), encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    plist_path = contents_dir / "Info.plist"
    plist_path.write_bytes(plistlib.dumps(_info_plist()))

    signing_identity = ""
    if adhoc_sign:
        _adhoc_sign_app(target)
        signing_identity = "-"

    return {
        "status": "ok",
        "app_path": str(target),
        "executable_path": str(executable),
        "zipapp_path": zipapp_result["artifact_path"],
        "info_plist_path": str(plist_path),
        "bundle_identifier": "com.zohartito.printpipe",
        "version": __version__,
        "default_launch_mode": "web-ui",
        "default_url": "http://127.0.0.1:8765/",
        "default_runs_dir": "~/PrintPipe/runs",
        "signed": adhoc_sign,
        "signing_identity": signing_identity,
        "notarized": False,
        "bundles_python_runtime": False,
        "bundles_bambu_studio": False,
    }


def _adhoc_sign_app(app_path: Path) -> None:
    codesign = shutil.which("codesign")
    if codesign is None:
        raise RuntimeError("codesign is required for ad-hoc macOS app signing")
    result = subprocess.run(
        [codesign, "--force", "--deep", "--sign", "-", str(app_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "codesign failed").strip()
        raise RuntimeError(message)


def _launcher_script() -> str:
    return """#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$#" -eq 0 ]; then
  HOST="${PRINTPIPE_HOST:-127.0.0.1}"
  PORT="${PRINTPIPE_PORT:-8765}"
  RUNS_DIR="${PRINTPIPE_RUNS_DIR:-$HOME/PrintPipe/runs}"
  URL="${PRINTPIPE_APP_URL:-http://$HOST:$PORT/}"
  if [ "${PRINTPIPE_APP_DRY_RUN:-0}" = "1" ]; then
    printf 'PrintPipe app launcher\\n'
    printf 'url: %s\\n' "$URL"
    printf 'command: python3 %s serve --host %s --port %s --runs-dir %s\\n' "$APP_DIR/Resources/printpipe.pyz" "$HOST" "$PORT" "$RUNS_DIR"
    exit 0
  fi
  mkdir -p "$RUNS_DIR"
  (
    sleep 1
    /usr/bin/open "$URL" >/dev/null 2>&1 || true
  ) &
  exec /usr/bin/env python3 "$APP_DIR/Resources/printpipe.pyz" serve --host "$HOST" --port "$PORT" --runs-dir "$RUNS_DIR"
fi
exec /usr/bin/env python3 "$APP_DIR/Resources/printpipe.pyz" "$@"
"""


def _info_plist() -> dict[str, Any]:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "PrintPipe",
        "CFBundleExecutable": "printpipe",
        "CFBundleIdentifier": "com.zohartito.printpipe",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "PrintPipe",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    }


__all__ = ["build_macos_app_bundle"]
