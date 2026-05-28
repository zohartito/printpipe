from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from printpipe.cli import build_parser, main


def _write_standalone_zip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("PrintPipe/PrintPipe.exe", "exe")
        archive.writestr("PrintPipe/_internal/python311.dll", "runtime")
        archive.writestr("PrintPipe/README.txt", "readme")


def test_build_windows_installer_package_runs_inno_and_signtool(
    tmp_path: Path,
) -> None:
    from printpipe.packaging.windows_installer import build_windows_installer_package

    standalone_zip = tmp_path / "PrintPipe-Windows-standalone.zip"
    output_path = tmp_path / "PrintPipeSetup.exe"
    _write_standalone_zip(standalone_zip)
    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "iscc":
            output_path.write_text("installer", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = build_windows_installer_package(
        standalone_zip=standalone_zip,
        output_path=output_path,
        iscc_command="iscc",
        signtool_command="signtool",
        certificate_subject="CN=Zohar Tito Code Signing, O=PrintPipe",
        runner=fake_runner,
    )

    assert result["status"] == "ok"
    assert result["installer_path"] == str(output_path)
    assert result["installer_kind"] == "inno_setup"
    assert result["signed"] is True
    assert result["signing_identity"] == "CN=Zohar Tito Code Signing, O=PrintPipe"
    assert result["bundles_python_runtime"] is True
    assert result["bundles_bambu_studio"] is False
    assert commands[0][0] == "iscc"
    assert commands[0][-1].endswith("PrintPipe.iss")
    assert commands[1] == [
        "signtool",
        "sign",
        "/n",
        "CN=Zohar Tito Code Signing, O=PrintPipe",
        "/fd",
        "SHA256",
        "/tr",
        "http://timestamp.digicert.com",
        "/td",
        "SHA256",
        str(output_path),
    ]


def test_cli_build_windows_installer_parser_accepts_signing_flags() -> None:
    args = build_parser().parse_args(
        [
            "build-windows-installer",
            "--standalone-zip",
            "dist/PrintPipe-Windows-standalone.zip",
            "--output",
            "dist/PrintPipeSetup.exe",
            "--iscc",
            "iscc",
            "--signtool",
            "signtool",
            "--certificate-subject",
            "CN=Zohar Tito Code Signing, O=PrintPipe",
        ]
    )

    assert args.command == "build-windows-installer"
    assert args.standalone_zip == Path("dist/PrintPipe-Windows-standalone.zip")
    assert args.output == Path("dist/PrintPipeSetup.exe")
    assert args.iscc == "iscc"
    assert args.signtool == "signtool"
    assert args.certificate_subject == "CN=Zohar Tito Code Signing, O=PrintPipe"


def test_cli_build_windows_installer_json_reports_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import printpipe.packaging.windows_installer as windows_installer

    standalone_zip = tmp_path / "PrintPipe-Windows-standalone.zip"
    output_path = tmp_path / "PrintPipeSetup.exe"
    _write_standalone_zip(standalone_zip)

    def fake_builder(**kwargs):
        Path(kwargs["output_path"]).write_text("installer", encoding="utf-8")
        return {
            "status": "ok",
            "installer_path": str(kwargs["output_path"]),
            "installer_kind": "inno_setup",
            "signed": True,
            "signing_identity": kwargs["certificate_subject"],
            "bundles_python_runtime": True,
            "bundles_bambu_studio": False,
            "size_bytes": 9,
        }

    monkeypatch.setattr(windows_installer, "build_windows_installer_package", fake_builder)

    exit_code = main(
        [
            "build-windows-installer",
            "--standalone-zip",
            str(standalone_zip),
            "--output",
            str(output_path),
            "--certificate-subject",
            "CN=Zohar Tito Code Signing, O=PrintPipe",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["installer_path"] == str(output_path)
    assert payload["signed"] is True
