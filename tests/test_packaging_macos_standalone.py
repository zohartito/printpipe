from __future__ import annotations

import json
import os
import plistlib
import stat
import subprocess
from pathlib import Path

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_fake_pyinstaller(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import plistlib
import stat
import sys
from pathlib import Path

args = sys.argv[1:]
distpath = Path(args[args.index("--distpath") + 1])
name = Path(args[-1]).stem
app = distpath / f"{name}.app"
macos_dir = app / "Contents" / "MacOS"
framework = app / "Contents" / "Frameworks" / "Python.framework"
macos_dir.mkdir(parents=True)
framework.mkdir(parents=True)
executable = macos_dir / name
executable.write_text("#!/bin/sh\\nprintf 'printpipe 0.1.0\\\\n'\\n", encoding="utf-8")
executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
(framework / "Python").write_text("runtime", encoding="utf-8")
resources = app / "Contents" / "Resources"
resources.mkdir(exist_ok=True)
(resources / "Python.framework").symlink_to("../Frameworks/Python.framework")
(app / "Contents" / "Info.plist").write_bytes(
    plistlib.dumps(
        {
            "CFBundleExecutable": name,
            "CFBundleName": name,
            "CFBundlePackageType": "APPL",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeExtensions": [
                        "stl",
                        "obj",
                        "3mf",
                    ]
                }
            ],
        }
    )
)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_build_macos_standalone_app_uses_pyinstaller_and_bundles_runtime(
    tmp_path: Path,
) -> None:
    from printpipe.packaging.macos_standalone import build_macos_standalone_app

    fake_pyinstaller = tmp_path / "fake-pyinstaller"
    _write_fake_pyinstaller(fake_pyinstaller)
    app_path = tmp_path / "PrintPipeStandalone.app"

    result = build_macos_standalone_app(
        project_root=REPO_ROOT,
        app_path=app_path,
        pyinstaller_command=str(fake_pyinstaller),
    )

    executable = app_path / "Contents" / "MacOS" / "PrintPipeStandalone"
    runtime = app_path / "Contents" / "Frameworks" / "Python.framework"
    runtime_link = app_path / "Contents" / "Resources" / "Python.framework"
    plist = plistlib.loads((app_path / "Contents" / "Info.plist").read_bytes())

    assert result["status"] == "ok"
    assert result["app_path"] == str(app_path)
    assert result["executable_path"] == str(executable)
    assert result["runtime_kind"] == "pyinstaller"
    assert result["bundles_python_runtime"] is True
    assert result["bundled_python_runtime_path"] == str(runtime)
    assert result["bundles_bambu_studio"] is False
    assert result["signed"] is False
    assert result["notarized"] is False
    assert executable.exists()
    assert executable.stat().st_mode & stat.S_IXUSR
    assert runtime.exists()
    assert runtime_link.is_symlink()
    assert plist["CFBundleExecutable"] == "PrintPipeStandalone"
    assert plist["CFBundleDocumentTypes"][0]["CFBundleTypeExtensions"][:3] == [
        "stl",
        "obj",
        "3mf",
    ]


def test_cli_build_macos_standalone_json_reports_runtime_bundle(
    tmp_path: Path,
    capsys,
) -> None:
    fake_pyinstaller = tmp_path / "fake-pyinstaller"
    _write_fake_pyinstaller(fake_pyinstaller)
    app_path = tmp_path / "dist" / "PrintPipeStandalone.app"

    exit_code = main(
        [
            "build-macos-standalone",
            "--output",
            str(app_path),
            "--pyinstaller",
            str(fake_pyinstaller),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["app_path"] == str(app_path)
    assert payload["bundles_python_runtime"] is True
    assert Path(payload["executable_path"]).exists()


def test_macos_standalone_entrypoint_supports_cli_and_app_dry_run(tmp_path: Path) -> None:
    from printpipe.packaging.macos_standalone import write_standalone_entrypoint

    entrypoint = tmp_path / "entry.py"

    write_standalone_entrypoint(entrypoint)

    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PRINTPIPE_APP_DRY_RUN": "1",
        "HOME": str(tmp_path / "home"),
    }
    version = subprocess.run(
        [os.environ.get("PYTHON", "python"), str(entrypoint), "--version"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    dry_run = subprocess.run(
        [os.environ.get("PYTHON", "python"), str(entrypoint)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert version.returncode == 0
    assert version.stdout.strip() == "printpipe 0.1.0"
    assert dry_run.returncode == 0
    assert "PrintPipe standalone app launcher" in dry_run.stdout
    assert "http://127.0.0.1:8765/" in dry_run.stdout


def test_macos_standalone_spec_contains_printpipe_metadata(tmp_path: Path) -> None:
    from printpipe.packaging.macos_standalone import write_standalone_spec

    entrypoint = tmp_path / "entry.py"
    entrypoint.write_text("from printpipe.cli import main\n", encoding="utf-8")
    spec = tmp_path / "PrintPipeStandalone.spec"

    write_standalone_spec(
        spec,
        entrypoint=entrypoint,
        project_root=REPO_ROOT,
        app_name="PrintPipeStandalone",
    )

    source = spec.read_text(encoding="utf-8")

    assert "com.zohartito.printpipe.standalone" in source
    assert "CFBundleDocumentTypes" in source
    assert "PrintPipeStandalone.app" in source
