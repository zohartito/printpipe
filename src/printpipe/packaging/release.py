"""Build a release folder containing current PrintPipe handoff artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.packaging.macos_dmg import build_macos_dmg_package
from printpipe.packaging.windows_portable import build_windows_portable_package
from printpipe.packaging.zipapp import build_zipapp_package


RELEASE_BOUNDARIES = [
    "No artifact bundles Python.",
    "No artifact bundles Bambu Studio.",
    "macOS artifacts are not Developer ID signed or notarized.",
    "Windows artifact is not a signed installer.",
    "Physical print validation is still recorded separately in run evidence packets.",
]


def build_release_bundle(
    *,
    project_root: str | Path = Path("."),
    output_dir: str | Path = Path("dist/release"),
    adhoc_sign: bool = False,
) -> dict[str, Any]:
    """Build current distributable artifacts and write a checksum manifest."""

    root = Path(project_root).expanduser().resolve()
    target = Path(output_dir).expanduser()
    if not target.is_absolute():
        target = root / target
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"release output exists and is not a directory: {target}")
        shutil.rmtree(target)
    target.mkdir(parents=True)

    zipapp = build_zipapp_package(project_root=root, output_path=target / "printpipe.pyz")
    macos_dmg = build_macos_dmg_package(
        project_root=root,
        output_path=target / "PrintPipe.dmg",
        adhoc_sign=adhoc_sign,
    )
    windows = build_windows_portable_package(
        project_root=root,
        output_path=target / "PrintPipe-Windows-portable.zip",
    )

    artifacts = [
        _artifact_manifest(
            kind="zipapp",
            path=target / "printpipe.pyz",
            metadata=zipapp,
            signed=False,
            notarized=False,
        ),
        _artifact_manifest(
            kind="macos_dmg",
            path=target / "PrintPipe.dmg",
            metadata=macos_dmg,
            signed=bool(macos_dmg["signed"]),
            notarized=False,
        ),
        _artifact_manifest(
            kind="windows_portable",
            path=target / "PrintPipe-Windows-portable.zip",
            metadata=windows,
            signed=False,
            notarized=False,
        ),
    ]

    manifest = {
        "status": "ok",
        "product": "PrintPipe",
        "version": __version__,
        "output_dir": str(target),
        "artifacts": artifacts,
        "boundaries": RELEASE_BOUNDARIES,
    }
    manifest_path = target / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "output_dir": str(target),
        "manifest_path": str(manifest_path),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "boundaries": RELEASE_BOUNDARIES,
    }


def verify_release_bundle(release_dir: str | Path) -> dict[str, Any]:
    """Verify a release folder against its checksum manifest."""

    root = Path(release_dir).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    root = root.resolve()
    manifest_path = root / "release_manifest.json"
    checks: list[dict[str, Any]] = []

    _append_check(
        checks,
        check_id="manifest_exists",
        ok=manifest_path.exists(),
        message="release_manifest.json exists",
        path=str(manifest_path),
    )
    if not manifest_path.exists():
        return _verification_payload(root=root, manifest_path=manifest_path, checks=checks)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _append_check(
            checks,
            check_id="manifest_json",
            ok=False,
            message=f"manifest is not valid JSON: {exc.msg}",
            path=str(manifest_path),
        )
        return _verification_payload(root=root, manifest_path=manifest_path, checks=checks)

    _append_check(
        checks,
        check_id="manifest_json",
        ok=True,
        message="manifest is valid JSON",
        path=str(manifest_path),
    )
    _append_check(
        checks,
        check_id="boundaries",
        ok=manifest.get("boundaries") == RELEASE_BOUNDARIES,
        message="release boundaries match current PrintPipe boundary claims",
        expected=RELEASE_BOUNDARIES,
        actual=manifest.get("boundaries"),
    )

    artifacts = manifest.get("artifacts")
    _append_check(
        checks,
        check_id="artifacts_list",
        ok=isinstance(artifacts, list),
        message="manifest artifacts is a list",
    )
    if not isinstance(artifacts, list):
        return _verification_payload(root=root, manifest_path=manifest_path, checks=checks)

    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            _append_check(
                checks,
                check_id=f"artifact_entry:{index}",
                ok=False,
                message="artifact entry is not an object",
            )
            continue
        _verify_artifact(root=root, artifact=artifact, index=index, checks=checks)

    return _verification_payload(
        root=root,
        manifest_path=manifest_path,
        checks=checks,
        artifact_count=len(artifacts),
    )


def _artifact_manifest(
    *,
    kind: str,
    path: Path,
    metadata: dict[str, Any],
    signed: bool,
    notarized: bool,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "signed": signed,
        "notarized": notarized,
        "bundles_python_runtime": bool(metadata["bundles_python_runtime"]),
        "bundles_bambu_studio": bool(metadata["bundles_bambu_studio"]),
    }


def _verify_artifact(
    *,
    root: Path,
    artifact: dict[str, Any],
    index: int,
    checks: list[dict[str, Any]],
) -> None:
    kind = str(artifact.get("kind") or f"artifact_{index}")
    rel_path = artifact.get("path")
    path_check_id = f"artifact_path:{kind}"
    if not isinstance(rel_path, str) or not rel_path:
        _append_check(
            checks,
            check_id=path_check_id,
            ok=False,
            message="artifact path is missing or not a string",
        )
        return
    if Path(rel_path).is_absolute():
        _append_check(
            checks,
            check_id=path_check_id,
            ok=False,
            message="artifact path must be relative to the release folder",
            path=rel_path,
        )
        return

    artifact_path = (root / rel_path).resolve()
    try:
        artifact_path.relative_to(root)
    except ValueError:
        _append_check(
            checks,
            check_id=path_check_id,
            ok=False,
            message="artifact path escapes the release folder",
            path=rel_path,
        )
        return

    _append_check(
        checks,
        check_id=path_check_id,
        ok=True,
        message="artifact path is inside the release folder",
        path=rel_path,
    )
    exists = artifact_path.exists()
    _append_check(
        checks,
        check_id=f"artifact_exists:{kind}",
        ok=exists,
        message="artifact exists",
        path=str(artifact_path),
    )
    if not exists:
        return

    expected_size = artifact.get("size_bytes")
    actual_size = artifact_path.stat().st_size
    _append_check(
        checks,
        check_id=f"artifact_size:{kind}",
        ok=expected_size == actual_size,
        message="artifact size matches manifest",
        expected=expected_size,
        actual=actual_size,
        path=str(artifact_path),
    )

    expected_sha = artifact.get("sha256")
    actual_sha = _sha256(artifact_path)
    _append_check(
        checks,
        check_id=f"artifact_sha256:{kind}",
        ok=expected_sha == actual_sha,
        message="artifact sha256 matches manifest",
        expected=expected_sha,
        actual=actual_sha,
        path=str(artifact_path),
    )


def _append_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    ok: bool,
    message: str,
    **extra: Any,
) -> None:
    check = {
        "id": check_id,
        "status": "ok" if ok else "failed",
        "message": message,
    }
    check.update(extra)
    checks.append(check)


def _verification_payload(
    *,
    root: Path,
    manifest_path: Path,
    checks: list[dict[str, Any]],
    artifact_count: int = 0,
) -> dict[str, Any]:
    failures = [check for check in checks if check["status"] != "ok"]
    return {
        "status": "failed" if failures else "ok",
        "release_dir": str(root),
        "manifest_path": str(manifest_path),
        "artifact_count": artifact_count,
        "checks": checks,
        "failures": failures,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["RELEASE_BOUNDARIES", "build_release_bundle", "verify_release_bundle"]
