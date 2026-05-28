from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

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
        return

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


def test_cli_build_release_json_reports_manifest(tmp_path: Path, capsys) -> None:
    if shutil.which("hdiutil") is None:
        return

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
