"""Build a release folder containing current PrintPipe handoff artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.packaging.macos_dmg import build_macos_dmg_package
from printpipe.packaging.macos_standalone import build_macos_standalone_app
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
    developer_id_identity: str | None = None,
    notary_profile: str | None = None,
    include_standalone: bool = False,
    pyinstaller_command: str = "pyinstaller",
    windows_standalone_zip: str | Path | None = None,
    windows_installer_exe: str | Path | None = None,
) -> dict[str, Any]:
    """Build current distributable artifacts and write a checksum manifest."""

    if adhoc_sign and developer_id_identity:
        raise ValueError("Choose either ad-hoc signing or Developer ID signing, not both")
    if notary_profile and not developer_id_identity:
        raise ValueError("macOS notarization requires a Developer ID signed app")

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
        developer_id_identity=developer_id_identity,
        notary_profile=notary_profile,
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
            notarized=bool(macos_dmg["notarized"]),
        ),
        _artifact_manifest(
            kind="windows_portable",
            path=target / "PrintPipe-Windows-portable.zip",
            metadata=windows,
            signed=False,
            notarized=False,
        ),
    ]
    if include_standalone:
        with tempfile.TemporaryDirectory(prefix="printpipe-release-standalone-") as temp_dir:
            standalone = build_macos_standalone_app(
                project_root=root,
                app_path=Path(temp_dir) / "PrintPipeStandalone.app",
                pyinstaller_command=pyinstaller_command,
                adhoc_sign=adhoc_sign,
            )
            standalone_zip = target / "PrintPipeStandalone-macOS.zip"
            _zip_directory(
                source_dir=Path(standalone["app_path"]),
                target=standalone_zip,
            )
        artifacts.append(
            _artifact_manifest(
                kind="macos_standalone_zip",
                path=target / "PrintPipeStandalone-macOS.zip",
                metadata=standalone,
                signed=bool(standalone["signed"]),
                notarized=False,
            )
        )
    if windows_standalone_zip is not None:
        source = Path(windows_standalone_zip).expanduser()
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.exists():
            raise FileNotFoundError(f"Windows standalone ZIP not found: {source}")
        if source.suffix.lower() != ".zip":
            raise ValueError("Windows standalone release artifact must be a .zip file")
        standalone_target = target / "PrintPipe-Windows-standalone.zip"
        shutil.copy2(source, standalone_target)
        artifacts.append(
            _artifact_manifest(
                kind="windows_standalone_zip",
                path=standalone_target,
                metadata=_windows_standalone_zip_metadata(standalone_target),
                signed=False,
                notarized=False,
            )
        )
    if windows_installer_exe is not None:
        source = Path(windows_installer_exe).expanduser()
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.exists():
            raise FileNotFoundError(f"Windows installer EXE not found: {source}")
        if source.suffix.lower() != ".exe":
            raise ValueError("Windows installer release artifact must be an .exe file")
        installer_target = target / "PrintPipeSetup.exe"
        shutil.copy2(source, installer_target)
        artifacts.append(
            _artifact_manifest(
                kind="windows_installer",
                path=installer_target,
                metadata=_windows_installer_metadata(),
                signed=True,
                notarized=False,
            )
        )

    manifest = {
        "status": "ok",
        "product": "PrintPipe",
        "version": __version__,
        "output_dir": str(target),
        "artifacts": artifacts,
        "boundaries": _release_boundaries(artifacts),
    }
    manifest_path = target / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "output_dir": str(target),
        "manifest_path": str(manifest_path),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "boundaries": manifest["boundaries"],
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
    expected_boundaries = _release_boundaries(_list_artifacts(manifest.get("artifacts")))
    _append_check(
        checks,
        check_id="boundaries",
        ok=manifest.get("boundaries") == expected_boundaries,
        message="release boundaries match current PrintPipe boundary claims",
        expected=expected_boundaries,
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
    artifact = {
        "kind": kind,
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "signed": signed,
        "notarized": notarized,
        "bundles_python_runtime": bool(metadata["bundles_python_runtime"]),
        "bundles_bambu_studio": bool(metadata["bundles_bambu_studio"]),
    }
    if metadata.get("signing_kind"):
        artifact["signing_kind"] = str(metadata["signing_kind"])
    return artifact


def _release_boundaries(artifacts: list[dict[str, Any]]) -> list[str]:
    runtime_artifacts = {
        str(artifact.get("kind"))
        for artifact in artifacts
        if bool(artifact.get("bundles_python_runtime"))
    }
    if not runtime_artifacts:
        runtime_boundary = "No artifact bundles Python."
    elif runtime_artifacts == {"macos_standalone_zip"}:
        runtime_boundary = "macOS standalone artifact bundles Python; other artifacts do not."
    elif runtime_artifacts == {"windows_standalone_zip"}:
        runtime_boundary = "Windows standalone artifact bundles Python; other artifacts do not."
    elif runtime_artifacts == {"macos_standalone_zip", "windows_standalone_zip"}:
        runtime_boundary = (
            "macOS and Windows standalone artifacts bundle Python; other artifacts do not."
        )
    else:
        runtime_boundary = "Some artifacts bundle Python; other artifacts do not."
    return [
        runtime_boundary,
        "No artifact bundles Bambu Studio.",
        _macos_signing_boundary(artifacts),
        _windows_signing_boundary(artifacts),
        "Physical print validation is still recorded separately in run evidence packets.",
    ]


def _macos_signing_boundary(artifacts: list[dict[str, Any]]) -> str:
    macos_artifacts = [
        artifact
        for artifact in artifacts
        if str(artifact.get("kind", "")).startswith("macos_")
    ]
    if any(bool(artifact.get("notarized")) for artifact in macos_artifacts):
        return "macOS DMG is Developer ID signed and notarized."
    if any(str(artifact.get("signing_kind")) == "developer_id_application" for artifact in macos_artifacts):
        return "macOS artifacts are Developer ID signed but not notarized."
    return "macOS artifacts are not Developer ID signed or notarized."


def _windows_signing_boundary(artifacts: list[dict[str, Any]]) -> str:
    if any(str(artifact.get("kind")) == "windows_installer" for artifact in artifacts):
        return "Windows signed installer is included in this release."
    return "Windows artifact is not a signed installer."


def _list_artifacts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _zip_directory(*, source_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            relative_path = path.relative_to(source_dir.parent).as_posix()
            if path.is_symlink():
                info = zipfile.ZipInfo(relative_path)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, os.readlink(path))
            elif path.is_file():
                archive.write(path, relative_path)


def _windows_standalone_zip_metadata(path: Path) -> dict[str, bool]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    has_executable = "PrintPipe/PrintPipe.exe" in names
    has_runtime = any(
        name.startswith("PrintPipe/_internal/")
        and (
            name.lower().endswith(".dll")
            or "python" in Path(name).name.lower()
            or Path(name).name == "base_library.zip"
        )
        for name in names
    )
    if not has_executable:
        raise ValueError("Windows standalone ZIP must contain PrintPipe/PrintPipe.exe")
    if not has_runtime:
        raise ValueError("Windows standalone ZIP must contain bundled Python runtime files")
    return {
        "bundles_python_runtime": True,
        "bundles_bambu_studio": False,
    }


def _windows_installer_metadata() -> dict[str, bool | str]:
    return {
        "installer_kind": "inno_setup",
        "bundles_python_runtime": True,
        "bundles_bambu_studio": False,
        "signing_kind": "authenticode",
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
    _verify_artifact_metadata(
        artifact=artifact,
        kind=kind,
        rel_path=rel_path,
        checks=checks,
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


def _verify_artifact_metadata(
    *,
    artifact: dict[str, Any],
    kind: str,
    rel_path: str,
    checks: list[dict[str, Any]],
) -> None:
    suffix = Path(rel_path).suffix.lower()
    if kind == "zipapp":
        _append_check(
            checks,
            check_id="artifact_metadata:zipapp:path",
            ok=suffix == ".pyz",
            message="zipapp release artifact path ends with .pyz",
            path=rel_path,
        )
        _append_check(
            checks,
            check_id="artifact_metadata:zipapp:runtime",
            ok=artifact.get("bundles_python_runtime") is False,
            message="zipapp artifact does not claim to bundle Python",
            actual=artifact.get("bundles_python_runtime"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:zipapp:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="zipapp artifact does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
        )
        return

    if kind == "macos_dmg":
        _append_check(
            checks,
            check_id="artifact_metadata:macos_dmg:path",
            ok=suffix == ".dmg",
            message="macOS DMG release artifact path ends with .dmg",
            path=rel_path,
        )
        notarized = artifact.get("notarized") is True
        _append_check(
            checks,
            check_id="artifact_metadata:macos_dmg:notarized_signed",
            ok=not notarized or artifact.get("signed") is True,
            message="notarized macOS DMG also carries signed=true",
            actual={
                "signed": artifact.get("signed"),
                "notarized": artifact.get("notarized"),
            },
        )
        _append_check(
            checks,
            check_id="artifact_metadata:macos_dmg:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="macOS DMG does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
        )
        return

    if kind == "macos_standalone_zip":
        _append_check(
            checks,
            check_id="artifact_metadata:macos_standalone_zip:path",
            ok=suffix == ".zip",
            message="macOS standalone release artifact path ends with .zip",
            path=rel_path,
        )
        _append_check(
            checks,
            check_id="artifact_metadata:macos_standalone_zip:runtime",
            ok=artifact.get("bundles_python_runtime") is True,
            message="macOS standalone ZIP claims to bundle Python",
            actual=artifact.get("bundles_python_runtime"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:macos_standalone_zip:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="macOS standalone ZIP does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
        )
        return

    if kind == "windows_portable":
        _append_check(
            checks,
            check_id="artifact_metadata:windows_portable:path",
            ok=suffix == ".zip",
            message="Windows portable release artifact path ends with .zip",
            path=rel_path,
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_portable:runtime",
            ok=artifact.get("bundles_python_runtime") is False,
            message="Windows portable artifact does not claim to bundle Python",
            actual=artifact.get("bundles_python_runtime"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_portable:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="Windows portable artifact does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
        )
        return

    if kind == "windows_standalone_zip":
        _append_check(
            checks,
            check_id="artifact_metadata:windows_standalone_zip:path",
            ok=suffix == ".zip",
            message="Windows standalone release artifact path ends with .zip",
            path=rel_path,
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_standalone_zip:runtime",
            ok=artifact.get("bundles_python_runtime") is True,
            message="Windows standalone ZIP claims to bundle Python",
            actual=artifact.get("bundles_python_runtime"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_standalone_zip:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="Windows standalone ZIP does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
        )
        return

    if kind == "windows_installer":
        _append_check(
            checks,
            check_id="artifact_metadata:windows_installer:path",
            ok=suffix == ".exe",
            message="Windows installer release artifact path ends with .exe",
            path=rel_path,
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_installer:signed",
            ok=artifact.get("signed") is True,
            message="Windows installer release artifact carries signed=true",
            actual=artifact.get("signed"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_installer:runtime",
            ok=artifact.get("bundles_python_runtime") is True,
            message="Windows installer claims to bundle Python runtime",
            actual=artifact.get("bundles_python_runtime"),
        )
        _append_check(
            checks,
            check_id="artifact_metadata:windows_installer:bambu",
            ok=artifact.get("bundles_bambu_studio") is False,
            message="Windows installer does not claim to bundle Bambu Studio",
            actual=artifact.get("bundles_bambu_studio"),
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
