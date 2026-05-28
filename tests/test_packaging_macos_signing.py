from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from printpipe.cli import build_parser, main


def test_sign_macos_path_invokes_developer_id_codesign_and_verify(tmp_path: Path) -> None:
    from printpipe.packaging.macos_signing import sign_macos_path

    app_path = tmp_path / "PrintPipe.app"
    app_path.mkdir()
    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = sign_macos_path(
        app_path,
        identity="Developer ID Application: Zohar Tito (TEAMID)",
        codesign_path="/usr/bin/codesign",
        runner=fake_runner,
    )

    assert result["status"] == "ok"
    assert result["path"] == str(app_path)
    assert result["identity"] == "Developer ID Application: Zohar Tito (TEAMID)"
    assert result["verified"] is True
    assert commands == [
        [
            "/usr/bin/codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--timestamp",
            "--sign",
            "Developer ID Application: Zohar Tito (TEAMID)",
            str(app_path),
        ],
        [
            "/usr/bin/codesign",
            "--verify",
            "--deep",
            "--strict",
            str(app_path),
        ],
    ]


def test_notarize_macos_artifact_submits_waits_and_staples(tmp_path: Path) -> None:
    from printpipe.packaging.macos_signing import notarize_macos_artifact

    dmg = tmp_path / "PrintPipe.dmg"
    dmg.write_text("dmg", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[1] == "notarytool":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"id": "submission-123", "status": "Accepted"}),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="stapled", stderr="")

    result = notarize_macos_artifact(
        dmg,
        keychain_profile="printpipe-notary",
        xcrun_path="/usr/bin/xcrun",
        runner=fake_runner,
    )

    assert result["status"] == "ok"
    assert result["artifact_path"] == str(dmg)
    assert result["submission_id"] == "submission-123"
    assert result["notary_status"] == "Accepted"
    assert result["stapled"] is True
    assert commands == [
        [
            "/usr/bin/xcrun",
            "notarytool",
            "submit",
            str(dmg),
            "--keychain-profile",
            "printpipe-notary",
            "--wait",
            "--output-format",
            "json",
        ],
        ["/usr/bin/xcrun", "stapler", "staple", str(dmg)],
    ]


def test_build_macos_app_bundle_accepts_developer_id_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.macos_app as macos_app

    signed_paths: list[tuple[Path, str]] = []

    def fake_sign(path: Path, *, identity: str, **_kwargs):
        signed_paths.append((path, identity))
        return {
            "status": "ok",
            "path": str(path),
            "identity": identity,
            "verified": True,
        }

    monkeypatch.setattr(macos_app, "sign_macos_path", fake_sign)

    result = macos_app.build_macos_app_bundle(
        project_root=Path(__file__).resolve().parents[1],
        app_path=tmp_path / "PrintPipe.app",
        developer_id_identity="Developer ID Application: Zohar Tito (TEAMID)",
    )

    assert result["signed"] is True
    assert result["signing_identity"] == "Developer ID Application: Zohar Tito (TEAMID)"
    assert result["signing_kind"] == "developer_id_application"
    assert result["notarized"] is False
    assert signed_paths == [
        (tmp_path / "PrintPipe.app", "Developer ID Application: Zohar Tito (TEAMID)")
    ]


def test_cli_build_macos_dmg_accepts_developer_id_and_notary_flags() -> None:
    args = build_parser().parse_args(
        [
            "build-macos-dmg",
            "--developer-id-identity",
            "Developer ID Application: Zohar Tito (TEAMID)",
            "--notary-profile",
            "printpipe-notary",
        ]
    )

    assert args.command == "build-macos-dmg"
    assert args.developer_id_identity == "Developer ID Application: Zohar Tito (TEAMID)"
    assert args.notary_profile == "printpipe-notary"


def test_build_macos_dmg_package_notarizes_developer_id_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.macos_dmg as macos_dmg

    notarized_paths: list[tuple[Path, str]] = []

    def fake_app_builder(**kwargs):
        app_path = Path(kwargs["app_path"])
        app_path.mkdir(parents=True)
        return {
            "signed": True,
            "signing_identity": kwargs["developer_id_identity"],
            "signing_kind": "developer_id_application",
            "bundles_python_runtime": False,
            "bundles_bambu_studio": False,
        }

    def fake_notarize(path: Path, *, keychain_profile: str):
        notarized_paths.append((path, keychain_profile))
        return {
            "status": "ok",
            "artifact_path": str(path),
            "submission_id": "submission-123",
            "notary_status": "Accepted",
            "stapled": True,
        }

    def fake_hdiutil(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_text("dmg", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(macos_dmg, "build_macos_app_bundle", fake_app_builder)
    monkeypatch.setattr(macos_dmg, "notarize_macos_artifact", fake_notarize)
    monkeypatch.setattr(macos_dmg.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(macos_dmg.subprocess, "run", fake_hdiutil)

    result = macos_dmg.build_macos_dmg_package(
        project_root=tmp_path,
        output_path=tmp_path / "PrintPipe.dmg",
        developer_id_identity="Developer ID Application: Zohar Tito (TEAMID)",
        notary_profile="printpipe-notary",
    )

    assert result["signed"] is True
    assert result["signing_kind"] == "developer_id_application"
    assert result["notarized"] is True
    assert result["stapled"] is True
    assert result["notary_profile"] == "printpipe-notary"
    assert notarized_paths == [(tmp_path / "PrintPipe.dmg", "printpipe-notary")]


def test_cli_build_macos_dmg_rejects_notary_without_developer_id(
    tmp_path: Path,
    capsys,
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "build-macos-dmg",
                "--output",
                str(tmp_path / "PrintPipe.dmg"),
                "--notary-profile",
                "printpipe-notary",
            ]
        )

    assert exc.value.code == 2
    assert "--notary-profile requires --developer-id-identity" in capsys.readouterr().err
