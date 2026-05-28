"""Build a portable Windows ZIP around the PrintPipe zipapp."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Any

from printpipe.packaging.zipapp import build_zipapp_package


def build_windows_portable_package(
    *,
    project_root: str | Path = Path("."),
    output_path: str | Path = Path("dist/PrintPipe-Windows-portable.zip"),
) -> dict[str, Any]:
    """Build a Windows-friendly ZIP with launch scripts and the zipapp."""

    root = Path(project_root).expanduser().resolve()
    target = Path(output_path).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.suffix.lower() != ".zip":
        raise ValueError("Windows portable package output must end with .zip")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    with tempfile.TemporaryDirectory(prefix="printpipe-windows-portable-") as temp_dir:
        staging = Path(temp_dir) / "PrintPipe"
        staging.mkdir()
        zipapp_result = build_zipapp_package(
            project_root=root,
            output_path=staging / "printpipe.pyz",
            interpreter="/usr/bin/env python3",
        )
        (staging / "printpipe.cmd").write_text(_cmd_launcher(), encoding="utf-8", newline="\r\n")
        (staging / "printpipe.ps1").write_text(_powershell_launcher(), encoding="utf-8")
        (staging / "install-start-menu.ps1").write_text(
            _start_menu_installer(),
            encoding="utf-8",
        )
        (staging / "uninstall-start-menu.ps1").write_text(
            _start_menu_uninstaller(),
            encoding="utf-8",
        )
        (staging / "README.txt").write_text(_readme(), encoding="utf-8")
        _write_zip_archive(source_dir=staging, target=target)

    return {
        "status": "ok",
        "archive_path": str(target),
        "archive_name": target.name,
        "root_folder": "PrintPipe",
        "zipapp_path": "PrintPipe/printpipe.pyz",
        "cmd_launcher": "PrintPipe/printpipe.cmd",
        "powershell_launcher": "PrintPipe/printpipe.ps1",
        "start_menu_installer": "PrintPipe/install-start-menu.ps1",
        "start_menu_uninstaller": "PrintPipe/uninstall-start-menu.ps1",
        "readme_path": "PrintPipe/README.txt",
        "contains_zipapp": True,
        "contains_cmd_launcher": True,
        "contains_powershell_launcher": True,
        "contains_start_menu_installer": True,
        "contains_start_menu_uninstaller": True,
        "signed": False,
        "notarized": False,
        "bundles_python_runtime": False,
        "bundles_bambu_studio": False,
        "size_bytes": target.stat().st_size,
        "zipapp_size_bytes": zipapp_result["size_bytes"],
    }


def _write_zip_archive(*, source_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent).as_posix())


def _cmd_launcher() -> str:
    return """@echo off
setlocal
python "%~dp0printpipe.pyz" %*
"""


def _powershell_launcher() -> str:
    return """$ErrorActionPreference = "Stop"
python "$PSScriptRoot\\printpipe.pyz" @args
"""


def _start_menu_installer() -> str:
    return """$ErrorActionPreference = "Stop"
$Programs = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\PrintPipe"
New-Item -ItemType Directory -Force -Path $Programs | Out-Null
$ShortcutPath = Join-Path $Programs "PrintPipe CLI.lnk"
$Target = Join-Path $env:ComSpec "..\\cmd.exe"
$Target = (Resolve-Path $Target).Path
$Launcher = Join-Path $PSScriptRoot "printpipe.cmd"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.Arguments = "/k `"$Launcher`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Open PrintPipe CLI"
$Shortcut.Save()
Write-Output "Installed Start Menu shortcut: $ShortcutPath"
"""


def _start_menu_uninstaller() -> str:
    return """$ErrorActionPreference = "Stop"
$Programs = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\PrintPipe"
$ShortcutPath = Join-Path $Programs "PrintPipe CLI.lnk"
Remove-Item -Force -Path $ShortcutPath -ErrorAction SilentlyContinue
if (Test-Path $Programs) {
    $Remaining = Get-ChildItem -Force -Path $Programs -ErrorAction SilentlyContinue
    if (-not $Remaining) {
        Remove-Item -Force -Path $Programs -ErrorAction SilentlyContinue
    }
}
Write-Output "Removed Start Menu shortcut: $ShortcutPath"
"""


def _readme() -> str:
    return """PrintPipe Windows Portable

This package contains:

- printpipe.pyz: the PrintPipe Python zipapp
- printpipe.cmd: Command Prompt launcher
- printpipe.ps1: PowerShell launcher
- install-start-menu.ps1: optional user Start Menu shortcut installer
- uninstall-start-menu.ps1: removes the optional Start Menu shortcut

Requirements:

- Python 3.11+ available as `python`
- Bambu Studio installed separately for live slice gates

Examples:

printpipe.cmd --version
printpipe.cmd package-smoke --platform windows --runs-dir runs\\package-smoke\\windows --json
powershell -ExecutionPolicy Bypass -File .\\printpipe.ps1 --version
powershell -ExecutionPolicy Bypass -File .\\install-start-menu.ps1
powershell -ExecutionPolicy Bypass -File .\\uninstall-start-menu.ps1

Boundaries:

- This is not a signed Windows installer.
- It does not bundle Python.
- It does not bundle Bambu Studio.
"""


__all__ = ["build_windows_portable_package"]
