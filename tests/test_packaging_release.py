from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from printpipe.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]


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
