from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from printpipe.cli import main
from printpipe.packaging.macos_app import build_macos_app_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_macos_app_bundle_wraps_zipapp_executable(tmp_path: Path) -> None:
    app_path = tmp_path / "PrintPipe.app"

    result = build_macos_app_bundle(project_root=REPO_ROOT, app_path=app_path)

    executable = app_path / "Contents" / "MacOS" / "printpipe"
    zipapp = app_path / "Contents" / "Resources" / "printpipe.pyz"
    plist_path = app_path / "Contents" / "Info.plist"

    assert result["status"] == "ok"
    assert result["app_path"] == str(app_path)
    assert result["signed"] is False
    assert result["notarized"] is False
    assert executable.exists()
    assert zipapp.exists()
    assert plist_path.exists()
    assert executable.stat().st_mode & 0o111

    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["CFBundleName"] == "PrintPipe"
    assert plist["CFBundleExecutable"] == "printpipe"
    assert plist["CFBundlePackageType"] == "APPL"

    proc = subprocess.run(
        [str(executable), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip() == "printpipe 0.1.0"

    smoke_proc = subprocess.run(
        [
            str(executable),
            "package-smoke",
            "--platform",
            "macos",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    smoke_payload = json.loads(smoke_proc.stdout)

    assert smoke_proc.returncode == 0
    assert smoke_payload["status"] == "ok"
    assert Path(smoke_payload["run_root"]).exists()


def test_macos_app_default_launch_opens_local_web_ui(tmp_path: Path) -> None:
    app_path = tmp_path / "PrintPipe.app"

    result = build_macos_app_bundle(project_root=REPO_ROOT, app_path=app_path)
    executable = Path(result["executable_path"])
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "PRINTPIPE_APP_DRY_RUN": "1",
    }

    proc = subprocess.run(
        [str(executable)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0
    assert "PrintPipe app launcher" in proc.stdout
    assert "http://127.0.0.1:8765/" in proc.stdout
    assert f"--runs-dir {home / 'PrintPipe' / 'runs'}" in proc.stdout
    assert result["default_launch_mode"] == "web-ui"


def test_cli_build_macos_app_json_reports_bundle(tmp_path: Path, capsys) -> None:
    app_path = tmp_path / "dist" / "PrintPipe.app"

    exit_code = main(["build-macos-app", "--output", str(app_path), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["app_path"] == str(app_path)
    assert Path(payload["executable_path"]).exists()


def test_build_macos_app_bundle_can_apply_ad_hoc_signature(tmp_path: Path) -> None:
    if shutil.which("codesign") is None:
        return

    app_path = tmp_path / "PrintPipe.app"

    result = build_macos_app_bundle(
        project_root=REPO_ROOT,
        app_path=app_path,
        adhoc_sign=True,
    )

    assert result["signed"] is True
    assert result["signing_identity"] == "-"
    verify = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(app_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert verify.returncode == 0
