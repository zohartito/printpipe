"""Build a PyInstaller-backed macOS app with a bundled Python runtime."""

from __future__ import annotations

import json
import os
import plistlib
import shlex
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.packaging.macos_app import DOCUMENT_EXTENSIONS, _adhoc_sign_app


DEFAULT_PYINSTALLER_COMMAND = "pyinstaller"


def build_macos_standalone_app(
    *,
    project_root: str | Path = Path("."),
    app_path: str | Path = Path("dist/PrintPipeStandalone.app"),
    pyinstaller_command: str | list[str] = DEFAULT_PYINSTALLER_COMMAND,
    adhoc_sign: bool = False,
) -> dict[str, Any]:
    """Build a `.app` bundle that includes a Python runtime via PyInstaller."""

    root = Path(project_root).expanduser().resolve()
    target = Path(app_path).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.suffix != ".app":
        raise ValueError("macOS standalone app output must end with .app")
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"macOS standalone output exists and is not a directory: {target}")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    app_name = target.stem
    with tempfile.TemporaryDirectory(prefix="printpipe-pyinstaller-") as temp_dir:
        temp_root = Path(temp_dir)
        entrypoint = temp_root / "printpipe_standalone_entry.py"
        write_standalone_entrypoint(entrypoint)
        dist_dir = temp_root / "dist"
        command = _pyinstaller_command(pyinstaller_command) + [
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--name",
            app_name,
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(temp_root / "work"),
            "--specpath",
            str(temp_root / "spec"),
            str(entrypoint),
        ]
        result = _run_pyinstaller(command, root=root)
        built_app = dist_dir / f"{app_name}.app"
        if not built_app.is_dir():
            raise RuntimeError(
                "PyInstaller finished but did not create the expected app bundle: "
                f"{built_app}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        shutil.copytree(built_app, target)

    _patch_info_plist(target, app_name=app_name)
    executable = target / "Contents" / "MacOS" / app_name
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    signing_identity = ""
    if adhoc_sign:
        _adhoc_sign_app(target)
        signing_identity = "-"

    runtime_path = _bundled_python_runtime_path(target)
    return {
        "status": "ok",
        "app_path": str(target),
        "executable_path": str(executable),
        "bundle_identifier": "com.zohartito.printpipe.standalone",
        "version": __version__,
        "runtime_kind": "pyinstaller",
        "bundles_python_runtime": runtime_path is not None,
        "bundled_python_runtime_path": str(runtime_path) if runtime_path is not None else None,
        "bundles_bambu_studio": False,
        "default_launch_mode": "web-ui",
        "default_url": "http://127.0.0.1:8765/",
        "document_launch_mode": "run-and-open-web-ui",
        "document_extensions": list(DOCUMENT_EXTENSIONS),
        "signed": adhoc_sign,
        "signing_identity": signing_identity,
        "notarized": False,
        "size_bytes": _directory_size(target),
    }


def write_standalone_entrypoint(path: str | Path) -> None:
    """Write the Python entrypoint used inside the standalone app."""

    Path(path).write_text(_standalone_entrypoint_source(), encoding="utf-8")


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


def _patch_info_plist(app_path: Path, *, app_name: str) -> None:
    plist_path = app_path / "Contents" / "Info.plist"
    plist = plistlib.loads(plist_path.read_bytes()) if plist_path.exists() else {}
    plist.update(
        {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": "PrintPipe",
            "CFBundleExecutable": app_name,
            "CFBundleIdentifier": "com.zohartito.printpipe.standalone",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": app_name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeExtensions": list(DOCUMENT_EXTENSIONS),
                    "CFBundleTypeName": "PrintPipe input",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                }
            ],
            "LSMinimumSystemVersion": "12.0",
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
        }
    )
    plist_path.write_bytes(plistlib.dumps(plist))


def _bundled_python_runtime_path(app_path: Path) -> Path | None:
    for path in app_path.rglob("Python.framework"):
        if path.is_dir():
            return path
    for path in app_path.rglob("python*"):
        if path.is_file() and "_internal" in path.parts:
            return path
    return None


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _standalone_entrypoint_source() -> str:
    return r'''from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from printpipe.cli import main


def _app_defaults() -> tuple[str, str, str, str]:
    host = os.environ.get("PRINTPIPE_HOST", "127.0.0.1")
    port = os.environ.get("PRINTPIPE_PORT", "8765")
    runs_dir = os.environ.get(
        "PRINTPIPE_RUNS_DIR",
        str(Path.home() / "PrintPipe" / "runs"),
    )
    url = os.environ.get("PRINTPIPE_APP_URL", f"http://{host}:{port}/")
    return host, port, runs_dir, url


def _open_later(url: str) -> None:
    subprocess.Popen(
        ["/bin/sh", "-c", "sleep 1; /usr/bin/open \"$1\" >/dev/null 2>&1 || true", "sh", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _launch_web_ui() -> int:
    host, port, runs_dir, url = _app_defaults()
    if os.environ.get("PRINTPIPE_APP_DRY_RUN") == "1":
        print("PrintPipe standalone app launcher")
        print(f"url: {url}")
        print(f"command: printpipe serve --host {host} --port {port} --runs-dir {runs_dir}")
        return 0
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    _open_later(url)
    return main(["serve", "--host", host, "--port", port, "--runs-dir", runs_dir])


def _launch_document(input_path: str) -> int:
    host, port, runs_dir, url = _app_defaults()
    material = os.environ.get("PRINTPIPE_MATERIAL", "Generic PLA")
    printer = os.environ.get("PRINTPIPE_PRINTER", "Bambu Lab P2S")
    use_case = os.environ.get("PRINTPIPE_USE_CASE", "print")
    if os.environ.get("PRINTPIPE_APP_DRY_RUN") == "1":
        print("PrintPipe standalone document launcher")
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
    _open_later(url)
    return main(["serve", "--host", host, "--port", port, "--runs-dir", runs_dir])


if len(sys.argv) == 1:
    raise SystemExit(_launch_web_ui())

if len(sys.argv) == 2 and Path(sys.argv[1]).is_file():
    raise SystemExit(_launch_document(sys.argv[1]))

raise SystemExit(main(sys.argv[1:]))
'''


__all__ = ["build_macos_standalone_app", "write_standalone_entrypoint"]
