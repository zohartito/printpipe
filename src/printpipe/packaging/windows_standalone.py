"""Build a PyInstaller-backed Windows ZIP with a bundled Python runtime."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_PYINSTALLER_COMMAND = "pyinstaller"


def build_windows_standalone_package(
    *,
    project_root: str | Path = Path("."),
    output_path: str | Path = Path("dist/PrintPipe-Windows-standalone.zip"),
    pyinstaller_command: str | list[str] = DEFAULT_PYINSTALLER_COMMAND,
) -> dict[str, Any]:
    """Build a Windows standalone ZIP using PyInstaller on a Windows host."""

    root = Path(project_root).expanduser().resolve()
    target = Path(output_path).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.suffix.lower() != ".zip":
        raise ValueError("Windows standalone package output must end with .zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    with tempfile.TemporaryDirectory(prefix="printpipe-windows-standalone-") as temp_dir:
        temp_root = Path(temp_dir)
        entrypoint = temp_root / "printpipe_windows_standalone_entry.py"
        write_windows_standalone_entrypoint(entrypoint)
        dist_dir = temp_root / "dist"
        command = _pyinstaller_command(pyinstaller_command) + [
            "--noconfirm",
            "--clean",
            "--onedir",
            "--console",
            "--name",
            "PrintPipe",
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(temp_root / "work"),
            "--specpath",
            str(temp_root / "spec"),
            str(entrypoint),
        ]
        _run_pyinstaller(command, root=root)
        bundle_dir = dist_dir / "PrintPipe"
        if not bundle_dir.is_dir():
            raise RuntimeError(
                "PyInstaller finished but did not create the expected bundle folder: "
                f"{bundle_dir}"
            )
        executable = _find_windows_executable(bundle_dir)
        bundles_python_runtime = _bundles_python_runtime(bundle_dir)
        (bundle_dir / "install-start-menu.ps1").write_text(
            _start_menu_installer(),
            encoding="utf-8",
        )
        (bundle_dir / "uninstall-start-menu.ps1").write_text(
            _start_menu_uninstaller(),
            encoding="utf-8",
        )
        (bundle_dir / "install-file-associations.ps1").write_text(
            _file_association_installer(),
            encoding="utf-8",
        )
        (bundle_dir / "uninstall-file-associations.ps1").write_text(
            _file_association_uninstaller(),
            encoding="utf-8",
        )
        (bundle_dir / "README.txt").write_text(_readme(), encoding="utf-8")
        _write_zip_archive(source_dir=bundle_dir, target=target)

    return {
        "status": "ok",
        "archive_path": str(target),
        "archive_name": target.name,
        "root_folder": "PrintPipe",
        "executable_path": f"PrintPipe/{executable.name}",
        "runtime_kind": "pyinstaller",
        "contains_executable": True,
        "contains_readme": True,
        "contains_start_menu_installer": True,
        "contains_start_menu_uninstaller": True,
        "contains_file_association_installer": True,
        "contains_file_association_uninstaller": True,
        "signed": False,
        "notarized": False,
        "bundles_python_runtime": bundles_python_runtime,
        "bundles_bambu_studio": False,
        "size_bytes": target.stat().st_size,
    }


def write_windows_standalone_entrypoint(path: str | Path) -> None:
    """Write the Python entrypoint used inside the Windows standalone app."""

    Path(path).write_text(_windows_standalone_entrypoint_source(), encoding="utf-8")


def _pyinstaller_command(command: str | list[str]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return list(command)


def _run_pyinstaller(
    command: list[str],
    *,
    root: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    source_path = str(root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else source_path + os.pathsep + existing_pythonpath
    )
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "PyInstaller command was not found. Install pyinstaller or pass "
            "--pyinstaller 'uvx --from pyinstaller pyinstaller'."
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            "PyInstaller failed with exit code "
            f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _find_windows_executable(bundle_dir: Path) -> Path:
    preferred = bundle_dir / "PrintPipe.exe"
    if preferred.exists():
        return preferred
    fallback = bundle_dir / "PrintPipe"
    if fallback.exists():
        return fallback
    raise RuntimeError(f"PrintPipe executable not found in PyInstaller output: {bundle_dir}")


def _bundles_python_runtime(bundle_dir: Path) -> bool:
    runtime_root = bundle_dir / "_internal"
    if not runtime_root.exists():
        return False
    for pattern in ("*.dll", "python*", "base_library.zip"):
        if any(runtime_root.rglob(pattern)):
            return True
    return False


def _write_zip_archive(*, source_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent).as_posix())


def _readme() -> str:
    return """PrintPipe Windows Standalone

This package contains a PyInstaller-built PrintPipe executable.

Optional helpers:

- install-start-menu.ps1: adds a user Start Menu shortcut for PrintPipe.exe
- uninstall-start-menu.ps1: removes the optional Start Menu shortcut
- install-file-associations.ps1: adds user file associations for mesh inputs
- uninstall-file-associations.ps1: removes PrintPipe-owned file associations

Examples:

PrintPipe.exe --version
PrintPipe.exe package-smoke --platform windows --runs-dir runs\\package-smoke\\windows --json
powershell -ExecutionPolicy Bypass -File .\\install-start-menu.ps1
powershell -ExecutionPolicy Bypass -File .\\uninstall-start-menu.ps1
powershell -ExecutionPolicy Bypass -File .\\install-file-associations.ps1
powershell -ExecutionPolicy Bypass -File .\\uninstall-file-associations.ps1

Boundaries:

- This bundles a Python runtime.
- This is not a signed Windows installer.
- It does not bundle Bambu Studio.
- Bambu Studio must be installed separately for live slice gates.
- File association install is opt-in and skips existing handlers unless -Force is used.
"""


def _start_menu_installer() -> str:
    return """$ErrorActionPreference = "Stop"
$Programs = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\PrintPipe"
New-Item -ItemType Directory -Force -Path $Programs | Out-Null
$ShortcutPath = Join-Path $Programs "PrintPipe.lnk"
$Launcher = Join-Path $PSScriptRoot "PrintPipe.exe"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Open PrintPipe"
$Shortcut.Save()
Write-Output "Installed Start Menu shortcut: $ShortcutPath"
"""


def _start_menu_uninstaller() -> str:
    return """$ErrorActionPreference = "Stop"
$Programs = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\PrintPipe"
$ShortcutPath = Join-Path $Programs "PrintPipe.lnk"
Remove-Item -Force -Path $ShortcutPath -ErrorAction SilentlyContinue
if (Test-Path $Programs) {
    $Remaining = Get-ChildItem -Force -Path $Programs -ErrorAction SilentlyContinue
    if (-not $Remaining) {
        Remove-Item -Force -Path $Programs -ErrorAction SilentlyContinue
    }
}
Write-Output "Removed Start Menu shortcut: $ShortcutPath"
"""


def _file_association_installer() -> str:
    return """param(
    [string[]]$Extensions = @(".stl", ".obj", ".3mf", ".glb", ".gltf"),
    [string]$ProgIdPrefix = "PrintPipe",
    [switch]$Force
)
# Default STL ProgID: PrintPipe.stl
$ErrorActionPreference = "Stop"
$ClassesRoot = "HKCU:\\Software\\Classes"
$Launcher = Join-Path $PSScriptRoot "PrintPipe.exe"
foreach ($Extension in $Extensions) {
    if (-not $Extension.StartsWith(".")) {
        $Extension = ".$Extension"
    }
    $ProgId = "$ProgIdPrefix$Extension"
    $ExtensionKey = Join-Path $ClassesRoot $Extension
    $ProgIdKey = Join-Path $ClassesRoot $ProgId
    New-Item -Force -Path $ExtensionKey | Out-Null
    $Current = (Get-Item -Path $ExtensionKey).GetValue("")
    if ($Current -and $Current -ne $ProgId -and -not $Force) {
        Write-Output "Skip existing association for $Extension -> $Current"
        continue
    }
    Set-Item -Path $ExtensionKey -Value $ProgId
    New-Item -Force -Path "$ProgIdKey\\shell\\open\\command" | Out-Null
    Set-Item -Path $ProgIdKey -Value "PrintPipe $Extension input"
    $Command = "`"$Launcher`" `"%1`""
    Set-Item -Path "$ProgIdKey\\shell\\open\\command" -Value $Command
    Write-Output "Installed file association for $Extension -> $ProgId"
}
"""


def _file_association_uninstaller() -> str:
    return """param(
    [string[]]$Extensions = @(".stl", ".obj", ".3mf", ".glb", ".gltf"),
    [string]$ProgIdPrefix = "PrintPipe"
)
# Default STL ProgID: PrintPipe.stl
$ErrorActionPreference = "Stop"
$ClassesRoot = "HKCU:\\Software\\Classes"
foreach ($Extension in $Extensions) {
    if (-not $Extension.StartsWith(".")) {
        $Extension = ".$Extension"
    }
    $ProgId = "$ProgIdPrefix$Extension"
    $ExtensionKey = Join-Path $ClassesRoot $Extension
    $ProgIdKey = Join-Path $ClassesRoot $ProgId
    $Current = if (Test-Path $ExtensionKey) { (Get-Item -Path $ExtensionKey).GetValue("") } else { $null }
    if ($Current -eq $ProgId) {
        Remove-Item -Recurse -Force -Path $ExtensionKey -ErrorAction SilentlyContinue
    }
    Remove-Item -Recurse -Force -Path $ProgIdKey -ErrorAction SilentlyContinue
    Write-Output "Removed file association for $Extension -> $ProgId"
}
"""


def _windows_standalone_entrypoint_source() -> str:
    return r'''from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

from printpipe.cli import main


def _app_defaults() -> tuple[str, str, str, str]:
    host = os.environ.get("PRINTPIPE_HOST", "127.0.0.1")
    port = os.environ.get("PRINTPIPE_PORT", "8765")
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    runs_dir = os.environ.get("PRINTPIPE_RUNS_DIR", str(home / "PrintPipe" / "runs"))
    url = os.environ.get("PRINTPIPE_APP_URL", f"http://{host}:{port}/")
    return host, port, runs_dir, url


def _launch_web_ui() -> int:
    host, port, runs_dir, url = _app_defaults()
    if os.environ.get("PRINTPIPE_APP_DRY_RUN") == "1":
        print("PrintPipe Windows standalone launcher")
        print(f"url: {url}")
        print(f"command: printpipe serve --host {host} --port {port} --runs-dir {runs_dir}")
        return 0
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    webbrowser.open(url)
    return main(["serve", "--host", host, "--port", port, "--runs-dir", runs_dir])


def _launch_document(input_path: str) -> int:
    host, port, runs_dir, url = _app_defaults()
    material = os.environ.get("PRINTPIPE_MATERIAL", "Generic PLA")
    printer = os.environ.get("PRINTPIPE_PRINTER", "Bambu Lab P2S")
    use_case = os.environ.get("PRINTPIPE_USE_CASE", "print")
    if os.environ.get("PRINTPIPE_APP_DRY_RUN") == "1":
        print("PrintPipe Windows standalone document launcher")
        print(f"url: {url}")
        print(
            "command: printpipe run "
            f"{input_path} --runs-dir {runs_dir} --material {material} "
            f"--printer {printer} --use-case {use_case}"
        )
        return 0
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    main(
        [
            "run",
            input_path,
            "--runs-dir",
            runs_dir,
            "--material",
            material,
            "--printer",
            printer,
            "--use-case",
            use_case,
        ]
    )
    webbrowser.open(url)
    return main(["serve", "--host", host, "--port", port, "--runs-dir", runs_dir])


if len(sys.argv) == 1:
    raise SystemExit(_launch_web_ui())

if len(sys.argv) == 2 and Path(sys.argv[1]).is_file():
    raise SystemExit(_launch_document(sys.argv[1]))

raise SystemExit(main(sys.argv[1:]))
'''


__all__ = ["build_windows_standalone_package", "write_windows_standalone_entrypoint"]
