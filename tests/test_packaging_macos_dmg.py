from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_macos_dmg_package_wraps_app_in_drag_install_image(tmp_path: Path) -> None:
    if shutil.which("hdiutil") is None:
        return

    from printpipe.packaging.macos_dmg import build_macos_dmg_package

    output_path = tmp_path / "PrintPipe.dmg"

    result = build_macos_dmg_package(
        project_root=REPO_ROOT,
        output_path=output_path,
        adhoc_sign=True,
    )

    assert result["status"] == "ok"
    assert result["dmg_path"] == str(output_path)
    assert result["app_name"] == "PrintPipe.app"
    assert result["contains_app"] is True
    assert result["contains_applications_link"] is True
    assert result["signed"] is True
    assert result["notarized"] is False
    assert result["drag_install"] is True
    assert output_path.exists()

    info = subprocess.run(
        ["hdiutil", "imageinfo", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert info.returncode == 0
    assert "Format Description" in info.stdout


def test_cli_build_macos_dmg_json_reports_distribution_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    if shutil.which("hdiutil") is None:
        return

    output_path = tmp_path / "dist" / "PrintPipe.dmg"

    exit_code = main(
        [
            "build-macos-dmg",
            "--output",
            str(output_path),
            "--adhoc-sign",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["dmg_path"] == str(output_path)
    assert payload["drag_install"] is True
