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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["RELEASE_BOUNDARIES", "build_release_bundle"]
