from __future__ import annotations

import json
import zipfile
from pathlib import Path

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_windows_portable_package_creates_launcher_zip(tmp_path: Path) -> None:
    from printpipe.packaging.windows_portable import build_windows_portable_package

    output_path = tmp_path / "PrintPipe-Windows-portable.zip"

    result = build_windows_portable_package(
        project_root=REPO_ROOT,
        output_path=output_path,
    )

    assert result["status"] == "ok"
    assert result["archive_path"] == str(output_path)
    assert result["archive_name"] == "PrintPipe-Windows-portable.zip"
    assert result["contains_zipapp"] is True
    assert result["contains_cmd_launcher"] is True
    assert result["contains_powershell_launcher"] is True
    assert result["contains_start_menu_installer"] is True
    assert result["contains_start_menu_uninstaller"] is True
    assert result["contains_file_association_installer"] is True
    assert result["contains_file_association_uninstaller"] is True
    assert result["signed"] is False
    assert result["bundles_python_runtime"] is False
    assert output_path.exists()

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        cmd = archive.read("PrintPipe/printpipe.cmd").decode("utf-8")
        ps1 = archive.read("PrintPipe/printpipe.ps1").decode("utf-8")
        installer = archive.read("PrintPipe/install-start-menu.ps1").decode("utf-8")
        uninstaller = archive.read("PrintPipe/uninstall-start-menu.ps1").decode("utf-8")
        assoc_installer = archive.read("PrintPipe/install-file-associations.ps1").decode(
            "utf-8"
        )
        assoc_uninstaller = archive.read("PrintPipe/uninstall-file-associations.ps1").decode(
            "utf-8"
        )

    assert "PrintPipe/printpipe.pyz" in names
    assert "PrintPipe/printpipe.cmd" in names
    assert "PrintPipe/printpipe.ps1" in names
    assert "PrintPipe/install-start-menu.ps1" in names
    assert "PrintPipe/uninstall-start-menu.ps1" in names
    assert "PrintPipe/install-file-associations.ps1" in names
    assert "PrintPipe/uninstall-file-associations.ps1" in names
    assert "PrintPipe/README.txt" in names
    assert "python \"%~dp0printpipe.pyz\" %*" in cmd
    assert 'python "$PSScriptRoot\\printpipe.pyz" @args' in ps1
    assert "WScript.Shell" in installer
    assert "Programs\\PrintPipe" in installer
    assert "PrintPipe CLI.lnk" in installer
    assert "Remove-Item" in uninstaller
    assert "PrintPipe CLI.lnk" in uninstaller
    assert "HKCU:\\Software\\Classes" in assoc_installer
    assert "Skip existing association" in assoc_installer
    assert "PrintPipe.stl" in assoc_installer
    assert "run" in assoc_installer
    assert "%1" in assoc_installer
    assert "PrintPipe.stl" in assoc_uninstaller
    assert "Remove-Item" in assoc_uninstaller


def test_cli_build_windows_portable_json_reports_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "dist" / "PrintPipe-Windows-portable.zip"

    exit_code = main(
        [
            "build-windows-portable",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["archive_path"] == str(output_path)
    assert payload["contains_cmd_launcher"] is True
    assert payload["contains_start_menu_installer"] is True
    assert payload["contains_file_association_installer"] is True
    assert output_path.exists()


def test_prp18_association_scripts_preserve_extension_keys_and_prior_defaults():
    from printpipe.packaging.windows_portable import _file_association_installer, _file_association_uninstaller
    import re

    install = _file_association_installer()
    uninstall = _file_association_uninstaller()
    destructive_extension_delete = bool(re.search(r'Remove-Item[^\n]+\$ExtensionKey', uninstall))
    assert destructive_extension_delete is False
    assert 'PrintPipePreviousDefault' in install
    assert 'PrintPipePreviousDefault' in uninstall
    assert 'GetValueKind' in install
    assert '.DeleteValue("", $false)' in uninstall
