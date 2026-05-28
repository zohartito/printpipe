from __future__ import annotations

import json
import os
import stat
import subprocess
import zipfile
from pathlib import Path

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_fake_pyinstaller(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import stat
import sys
from pathlib import Path

args = sys.argv[1:]
distpath = Path(args[args.index("--distpath") + 1])
name = args[args.index("--name") + 1]
bundle = distpath / name
internal = bundle / "_internal"
internal.mkdir(parents=True)
executable = bundle / "PrintPipe.exe"
executable.write_text("#!/bin/sh\\nprintf 'printpipe 0.1.0\\\\n'\\n", encoding="utf-8")
executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
(internal / "python311.dll").write_text("runtime", encoding="utf-8")
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_build_windows_standalone_package_zips_pyinstaller_runtime(
    tmp_path: Path,
) -> None:
    from printpipe.packaging.windows_standalone import build_windows_standalone_package

    fake_pyinstaller = tmp_path / "fake-pyinstaller"
    _write_fake_pyinstaller(fake_pyinstaller)
    output_path = tmp_path / "PrintPipe-Windows-standalone.zip"

    result = build_windows_standalone_package(
        project_root=REPO_ROOT,
        output_path=output_path,
        pyinstaller_command=str(fake_pyinstaller),
    )

    assert result["status"] == "ok"
    assert result["archive_path"] == str(output_path)
    assert result["archive_name"] == "PrintPipe-Windows-standalone.zip"
    assert result["root_folder"] == "PrintPipe"
    assert result["executable_path"] == "PrintPipe/PrintPipe.exe"
    assert result["runtime_kind"] == "pyinstaller"
    assert result["bundles_python_runtime"] is True
    assert result["bundles_bambu_studio"] is False
    assert result["signed"] is False
    assert output_path.exists()

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        readme = archive.read("PrintPipe/README.txt").decode("utf-8")

    assert "PrintPipe/PrintPipe.exe" in names
    assert "PrintPipe/_internal/python311.dll" in names
    assert "PrintPipe/README.txt" in names
    assert "bundles a Python runtime" in readme
    assert "not a signed Windows installer" in readme


def test_cli_build_windows_standalone_json_reports_runtime_bundle(
    tmp_path: Path,
    capsys,
) -> None:
    fake_pyinstaller = tmp_path / "fake-pyinstaller"
    _write_fake_pyinstaller(fake_pyinstaller)
    output_path = tmp_path / "dist" / "PrintPipe-Windows-standalone.zip"

    exit_code = main(
        [
            "build-windows-standalone",
            "--output",
            str(output_path),
            "--pyinstaller",
            str(fake_pyinstaller),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["archive_path"] == str(output_path)
    assert payload["bundles_python_runtime"] is True
    assert output_path.exists()


def test_windows_standalone_entrypoint_supports_cli_and_app_dry_run(tmp_path: Path) -> None:
    from printpipe.packaging.windows_standalone import write_windows_standalone_entrypoint

    entrypoint = tmp_path / "entry.py"

    write_windows_standalone_entrypoint(entrypoint)

    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PRINTPIPE_APP_DRY_RUN": "1",
        "USERPROFILE": str(tmp_path / "home"),
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
    assert "PrintPipe Windows standalone launcher" in dry_run.stdout
    assert "http://127.0.0.1:8765/" in dry_run.stdout
