from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path

import pytest

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_fake_release(tmp_path: Path) -> Path:
    from printpipe.packaging.release import RELEASE_BOUNDARIES

    release_dir = tmp_path / "release"
    release_dir.mkdir()
    artifact_specs = [
        ("zipapp", "printpipe.pyz", b"zipapp-bytes"),
        ("macos_dmg", "PrintPipe.dmg", b"dmg-bytes"),
        ("windows_portable", "PrintPipe-Windows-portable.zip", b"windows-bytes"),
    ]
    artifacts = []
    for kind, filename, contents in artifact_specs:
        artifact_path = release_dir / filename
        artifact_path.write_bytes(contents)
        artifacts.append(
            {
                "kind": kind,
                "path": filename,
                "size_bytes": artifact_path.stat().st_size,
                "sha256": hashlib.sha256(contents).hexdigest(),
                "signed": kind == "macos_dmg",
                "notarized": False,
                "bundles_python_runtime": False,
                "bundles_bambu_studio": False,
            }
        )
    manifest = {
        "status": "ok",
        "product": "PrintPipe",
        "version": "0.1.0-test",
        "output_dir": str(release_dir),
        "artifacts": artifacts,
        "boundaries": RELEASE_BOUNDARIES,
    }
    (release_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return release_dir


def test_build_release_bundle_writes_manifest_with_checksums(tmp_path: Path) -> None:
    if shutil.which("hdiutil") is None:
        pytest.skip("native macOS hdiutil is unavailable")

    from printpipe.packaging.release import build_release_bundle

    output_dir = tmp_path / "release"

    result = build_release_bundle(
        project_root=REPO_ROOT,
        output_dir=output_dir,
        adhoc_sign=True,
    )
    manifest = json.loads((output_dir / "release_manifest.json").read_text(encoding="utf-8"))
    artifacts = {artifact["kind"]: artifact for artifact in manifest["artifacts"]}

    assert result["status"] == "ok"
    assert result["output_dir"] == str(output_dir)
    assert result["manifest_path"] == str(output_dir / "release_manifest.json")
    assert set(artifacts) == {"zipapp", "macos_dmg", "windows_portable"}
    assert artifacts["zipapp"]["path"] == "printpipe.pyz"
    assert artifacts["macos_dmg"]["path"] == "PrintPipe.dmg"
    assert artifacts["windows_portable"]["path"] == "PrintPipe-Windows-portable.zip"
    assert artifacts["macos_dmg"]["signed"] is True
    assert artifacts["macos_dmg"]["notarized"] is False
    assert manifest["boundaries"] == [
        "No artifact bundles Python.",
        "No artifact bundles Bambu Studio.",
        "macOS artifacts are not Developer ID signed or notarized.",
        "Windows artifact is not a signed installer.",
        "Physical print validation is still recorded separately in run evidence packets.",
    ]
    for artifact in artifacts.values():
        artifact_path = output_dir / artifact["path"]
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        assert artifact_path.exists()
        assert artifact["size_bytes"] == artifact_path.stat().st_size
        assert artifact["sha256"] == digest


def test_build_release_bundle_can_include_macos_standalone_runtime_zip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if shutil.which("hdiutil") is None:
        pytest.skip("native macOS hdiutil is unavailable")

    import printpipe.packaging.release as release

    def fake_standalone_builder(
        *,
        project_root: str | Path,
        app_path: str | Path,
        pyinstaller_command: str,
        adhoc_sign: bool,
    ) -> dict[str, object]:
        app = Path(app_path)
        executable = app / "Contents" / "MacOS" / "PrintPipeStandalone"
        runtime = app / "Contents" / "Frameworks" / "Python.framework"
        runtime_link = app / "Contents" / "Resources" / "Python.framework"
        executable.parent.mkdir(parents=True)
        runtime.mkdir(parents=True)
        runtime_link.parent.mkdir(parents=True)
        runtime_link.symlink_to("../Frameworks/Python.framework")
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        (runtime / "Python").write_text("runtime", encoding="utf-8")
        return {
            "status": "ok",
            "app_path": str(app),
            "executable_path": str(executable),
            "runtime_kind": "pyinstaller",
            "bundles_python_runtime": True,
            "bundled_python_runtime_path": str(runtime),
            "bundles_bambu_studio": False,
            "signed": adhoc_sign,
            "notarized": False,
        }

    monkeypatch.setattr(release, "build_macos_standalone_app", fake_standalone_builder)
    output_dir = tmp_path / "release"

    result = release.build_release_bundle(
        project_root=REPO_ROOT,
        output_dir=output_dir,
        adhoc_sign=True,
        include_standalone=True,
        pyinstaller_command="fake-pyinstaller",
    )
    manifest = json.loads((output_dir / "release_manifest.json").read_text(encoding="utf-8"))
    artifacts = {artifact["kind"]: artifact for artifact in manifest["artifacts"]}

    assert result["artifact_count"] == 4
    assert artifacts["macos_standalone_zip"]["path"] == "PrintPipeStandalone-macOS.zip"
    assert artifacts["macos_standalone_zip"]["signed"] is True
    assert artifacts["macos_standalone_zip"]["bundles_python_runtime"] is True
    assert artifacts["macos_standalone_zip"]["bundles_bambu_studio"] is False
    with zipfile.ZipFile(output_dir / "PrintPipeStandalone-macOS.zip") as archive:
        names = archive.namelist()
        runtime_link_info = archive.getinfo(
            "PrintPipeStandalone.app/Contents/Resources/Python.framework"
        )
    assert "PrintPipeStandalone.app/Contents/MacOS/PrintPipeStandalone" in names
    assert any(name.startswith("PrintPipeStandalone.app/Contents/Frameworks/Python.framework") for name in names)
    assert stat.S_IFMT(runtime_link_info.external_attr >> 16) == stat.S_IFLNK


def test_build_release_bundle_can_include_prebuilt_windows_standalone_zip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.release as release

    def fake_zipapp_builder(*, project_root: str | Path, output_path: str | Path) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("zipapp", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    def fake_dmg_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
        adhoc_sign: bool,
        developer_id_identity: str | None,
        notary_profile: str | None,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("dmg", encoding="utf-8")
        return {
            "bundles_python_runtime": False,
            "bundles_bambu_studio": False,
            "signed": adhoc_sign,
            "notarized": False,
        }

    def fake_windows_portable_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("windows portable", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    monkeypatch.setattr(release, "build_zipapp_package", fake_zipapp_builder)
    monkeypatch.setattr(release, "build_macos_dmg_package", fake_dmg_builder)
    monkeypatch.setattr(release, "build_windows_portable_package", fake_windows_portable_builder)
    prebuilt = tmp_path / "prebuilt" / "PrintPipe-Windows-standalone.zip"
    prebuilt.parent.mkdir()
    with zipfile.ZipFile(prebuilt, "w") as archive:
        archive.writestr("PrintPipe/PrintPipe.exe", "exe")
        archive.writestr("PrintPipe/_internal/python311.dll", "runtime")
        archive.writestr("PrintPipe/README.txt", "readme")
    output_dir = tmp_path / "release"

    result = release.build_release_bundle(
        project_root=REPO_ROOT,
        output_dir=output_dir,
        windows_standalone_zip=prebuilt,
    )
    manifest = json.loads((output_dir / "release_manifest.json").read_text(encoding="utf-8"))
    artifacts = {artifact["kind"]: artifact for artifact in manifest["artifacts"]}

    assert result["artifact_count"] == 4
    assert artifacts["windows_standalone_zip"]["path"] == "PrintPipe-Windows-standalone.zip"
    assert artifacts["windows_standalone_zip"]["signed"] is False
    assert artifacts["windows_standalone_zip"]["notarized"] is False
    assert artifacts["windows_standalone_zip"]["bundles_python_runtime"] is True
    assert artifacts["windows_standalone_zip"]["bundles_bambu_studio"] is False
    assert (output_dir / "PrintPipe-Windows-standalone.zip").read_bytes() == prebuilt.read_bytes()
    assert "Windows standalone artifact bundles Python; other artifacts do not." in manifest[
        "boundaries"
    ]


def test_cli_build_release_json_reports_manifest(tmp_path: Path, capsys) -> None:
    if shutil.which("hdiutil") is None:
        pytest.skip("native macOS hdiutil is unavailable")

    output_dir = tmp_path / "dist" / "release"

    exit_code = main(
        [
            "build-release",
            "--output-dir",
            str(output_dir),
            "--adhoc-sign",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["output_dir"] == str(output_dir)
    assert Path(payload["manifest_path"]).exists()


def test_cli_build_release_parser_accepts_standalone_options() -> None:
    from printpipe.cli import build_parser

    args = build_parser().parse_args(
        [
            "build-release",
            "--include-standalone",
            "--pyinstaller",
            "uvx --from pyinstaller pyinstaller",
        ]
    )

    assert args.command == "build-release"
    assert args.include_standalone is True
    assert args.pyinstaller == "uvx --from pyinstaller pyinstaller"


def test_cli_build_release_parser_accepts_windows_standalone_zip() -> None:
    from printpipe.cli import build_parser

    args = build_parser().parse_args(
        [
            "build-release",
            "--windows-standalone-zip",
            "dist/PrintPipe-Windows-standalone.zip",
        ]
    )

    assert args.command == "build-release"
    assert args.windows_standalone_zip == Path("dist/PrintPipe-Windows-standalone.zip")


def test_build_release_bundle_can_include_prebuilt_windows_installer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.release as release

    def fake_zipapp_builder(*, project_root: str | Path, output_path: str | Path) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("zipapp", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    def fake_dmg_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
        adhoc_sign: bool,
        developer_id_identity: str | None,
        notary_profile: str | None,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("dmg", encoding="utf-8")
        return {
            "bundles_python_runtime": False,
            "bundles_bambu_studio": False,
            "signed": adhoc_sign,
            "notarized": False,
        }

    def fake_windows_portable_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("windows portable", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    monkeypatch.setattr(release, "build_zipapp_package", fake_zipapp_builder)
    monkeypatch.setattr(release, "build_macos_dmg_package", fake_dmg_builder)
    monkeypatch.setattr(release, "build_windows_portable_package", fake_windows_portable_builder)
    prebuilt = tmp_path / "prebuilt" / "PrintPipeSetup.exe"
    prebuilt.parent.mkdir()
    prebuilt.write_text("prebuilt installer", encoding="utf-8")

    result = release.build_release_bundle(
        project_root=REPO_ROOT,
        output_dir=tmp_path / "release",
        windows_installer_exe=prebuilt,
    )
    artifacts = {artifact["kind"]: artifact for artifact in result["artifacts"]}

    assert artifacts["windows_installer"]["path"] == "PrintPipeSetup.exe"
    assert artifacts["windows_installer"]["signed"] is False
    assert artifacts["windows_installer"]["bundles_python_runtime"] is True
    assert artifacts["windows_installer"]["bundles_bambu_studio"] is False
    assert "signing_kind" not in artifacts["windows_installer"]
    assert "Windows artifact is not a signed installer." in result["boundaries"]


def test_build_release_bundle_can_request_developer_id_notarized_dmg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.release as release

    def fake_zipapp_builder(*, project_root: str | Path, output_path: str | Path) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("zipapp", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    def fake_dmg_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
        adhoc_sign: bool,
        developer_id_identity: str | None,
        notary_profile: str | None,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("notarized dmg", encoding="utf-8")
        return {
            "bundles_python_runtime": False,
            "bundles_bambu_studio": False,
            "signed": True,
            "signing_identity": developer_id_identity,
            "signing_kind": "developer_id_application",
            "notarized": True,
            "notary_profile": notary_profile,
            "stapled": True,
        }

    def fake_windows_portable_builder(
        *,
        project_root: str | Path,
        output_path: str | Path,
    ) -> dict[str, object]:
        path = Path(output_path)
        path.write_text("windows portable", encoding="utf-8")
        return {"bundles_python_runtime": False, "bundles_bambu_studio": False}

    monkeypatch.setattr(release, "build_zipapp_package", fake_zipapp_builder)
    monkeypatch.setattr(release, "build_macos_dmg_package", fake_dmg_builder)
    monkeypatch.setattr(release, "build_windows_portable_package", fake_windows_portable_builder)

    result = release.build_release_bundle(
        project_root=REPO_ROOT,
        output_dir=tmp_path / "release",
        developer_id_identity="Developer ID Application: Zohar Tito (TEAMID)",
        notary_profile="printpipe-notary",
    )

    artifacts = {artifact["kind"]: artifact for artifact in result["artifacts"]}
    assert artifacts["macos_dmg"]["signed"] is True
    assert artifacts["macos_dmg"]["notarized"] is True
    assert "macOS DMG is Developer ID signed and notarized." in result["boundaries"]
    assert "macOS artifacts are not Developer ID signed or notarized." not in result["boundaries"]


def test_verify_release_bundle_accepts_manifest_and_artifact_hashes(tmp_path: Path) -> None:
    from printpipe.packaging.release import verify_release_bundle

    release_dir = _write_fake_release(tmp_path)

    result = verify_release_bundle(release_dir)

    assert result["status"] == "ok"
    assert result["release_dir"] == str(release_dir)
    assert result["manifest_path"] == str(release_dir / "release_manifest.json")
    assert result["artifact_count"] == 3
    assert result["failures"] == []
    assert {check["id"] for check in result["checks"]} >= {
        "manifest_exists",
        "manifest_json",
        "boundaries",
        "artifact_exists:zipapp",
        "artifact_size:zipapp",
        "artifact_sha256:zipapp",
    }


def test_verify_release_bundle_rejects_tampered_artifact(tmp_path: Path) -> None:
    from printpipe.packaging.release import verify_release_bundle

    release_dir = _write_fake_release(tmp_path)
    (release_dir / "printpipe.pyz").write_bytes(b"changed-after-manifest")

    result = verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "artifact_sha256:zipapp" in {failure["id"] for failure in result["failures"]}


def test_verify_release_bundle_rejects_boundary_drift(tmp_path: Path) -> None:
    from printpipe.packaging.release import verify_release_bundle

    release_dir = _write_fake_release(tmp_path)
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["boundaries"] = manifest["boundaries"][:-1]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    result = verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "boundaries" in {failure["id"] for failure in result["failures"]}


def test_verify_release_bundle_accepts_honest_unsigned_windows_installer_metadata(
    tmp_path: Path,
) -> None:
    import printpipe.packaging.release as release

    release_dir = _write_fake_release(tmp_path)
    installer = release_dir / "PrintPipeSetup.exe"
    installer.write_bytes(b"installer")
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "kind": "windows_installer",
            "path": installer.name,
            "size_bytes": installer.stat().st_size,
            "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
            "signed": False,
            "notarized": False,
            "bundles_python_runtime": True,
            "bundles_bambu_studio": False,
        }
    )
    manifest["boundaries"] = release._release_boundaries(manifest["artifacts"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    result = release.verify_release_bundle(release_dir)

    assert result["status"] == "ok"
    assert "artifact_metadata:windows_installer:signed" not in {
        failure["id"] for failure in result["failures"]
    }


def test_verify_release_bundle_rejects_unverifiable_signed_windows_installer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.release as release

    release_dir = _write_fake_release(tmp_path)
    installer = release_dir / "PrintPipeSetup.exe"
    installer.write_bytes(b"installer")
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "kind": "windows_installer",
            "path": installer.name,
            "size_bytes": installer.stat().st_size,
            "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
            "signed": True,
            "notarized": False,
            "bundles_python_runtime": True,
            "bundles_bambu_studio": False,
            "signing_kind": "authenticode",
        }
    )
    manifest["boundaries"] = release._release_boundaries(manifest["artifacts"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(release.shutil, "which", lambda _name: None)

    result = release.verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "artifact_signature:windows_installer:authenticode" in {
        failure["id"] for failure in result["failures"]
    }


def test_verify_release_bundle_rejects_windows_installer_wrong_extension(
    tmp_path: Path,
) -> None:
    import printpipe.packaging.release as release

    release_dir = _write_fake_release(tmp_path)
    installer = release_dir / "PrintPipeSetup.zip"
    installer.write_bytes(b"installer")
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "kind": "windows_installer",
            "path": installer.name,
            "size_bytes": installer.stat().st_size,
            "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
            "signed": True,
            "notarized": False,
            "bundles_python_runtime": True,
            "bundles_bambu_studio": False,
        }
    )
    manifest["boundaries"] = release._release_boundaries(manifest["artifacts"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    result = release.verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "artifact_metadata:windows_installer:path" in {
        failure["id"] for failure in result["failures"]
    }


def test_verify_release_bundle_rejects_notarized_macos_dmg_without_signed_flag(
    tmp_path: Path,
) -> None:
    import printpipe.packaging.release as release

    release_dir = _write_fake_release(tmp_path)
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    macos_dmg = next(
        artifact for artifact in manifest["artifacts"] if artifact["kind"] == "macos_dmg"
    )
    macos_dmg["signed"] = False
    macos_dmg["notarized"] = True
    macos_dmg["signing_kind"] = "developer_id_application"
    manifest["boundaries"] = release._release_boundaries(manifest["artifacts"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    result = release.verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "artifact_metadata:macos_dmg:notarized_signed" in {
        failure["id"] for failure in result["failures"]
    }


def test_verify_release_bundle_rejects_unverifiable_notarized_macos_dmg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import printpipe.packaging.release as release

    release_dir = _write_fake_release(tmp_path)
    manifest_path = release_dir / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    macos_dmg = next(
        artifact for artifact in manifest["artifacts"] if artifact["kind"] == "macos_dmg"
    )
    macos_dmg["signed"] = True
    macos_dmg["notarized"] = True
    macos_dmg["signing_kind"] = "developer_id_application"
    manifest["boundaries"] = release._release_boundaries(manifest["artifacts"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(release.shutil, "which", lambda _name: None)

    result = release.verify_release_bundle(release_dir)

    assert result["status"] == "failed"
    assert "artifact_notarization_verify:macos_dmg" in {
        failure["id"] for failure in result["failures"]
    }


def test_cli_verify_release_json_reports_ok(tmp_path: Path, capsys) -> None:
    release_dir = _write_fake_release(tmp_path)

    exit_code = main(["verify-release", str(release_dir), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["artifact_count"] == 3


def test_cli_verify_release_json_returns_two_on_failed_verification(
    tmp_path: Path,
    capsys,
) -> None:
    release_dir = _write_fake_release(tmp_path)
    (release_dir / "PrintPipe.dmg").unlink()

    exit_code = main(["verify-release", str(release_dir), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert "artifact_exists:macos_dmg" in {failure["id"] for failure in payload["failures"]}
