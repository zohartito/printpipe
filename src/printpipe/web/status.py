"""Status/progress helpers for the local PrintPipe web UI."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


FINISHED_STAGE_STATUSES = frozenset({"succeeded", "failed", "skipped"})
PENDING_STAGE_STATUSES = frozenset({"pending", "unknown"})
REPORT_FILES = {
    "json": "run_report.json",
    "markdown": "run_report.md",
    "html": "run_report.html",
}


def build_run_status(run_root: str | Path) -> dict[str, Any]:
    """Build a stable JSON-friendly status model for a run folder."""

    root = Path(run_root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    reports_dir = root / "80_reports"
    report_json_path = reports_dir / REPORT_FILES["json"]

    manifest, manifest_state = _read_json_document(manifest_path)
    report, report_state = _read_json_document(report_json_path)
    stages = _stage_models(manifest=manifest, report=report, run_root=root)
    artifacts = _artifact_models(_report_artifacts(report), run_root=root)
    warnings = _warning_items(report)

    return {
        "schema_version": 1,
        "run_id": _run_id(root, manifest, report),
        "run_root": str(root),
        "manifest": {
            "state": manifest_state,
            "present": manifest_state == "present",
            "path": str(manifest_path),
        },
        "input": _input_model(manifest),
        "report": {
            "state": report_state,
            **{
                key: _file_presence(reports_dir / filename, run_root=root)
                for key, filename in REPORT_FILES.items()
            },
        },
        "stages": stages,
        "progress": _progress_model(
            stages,
            manifest_state=manifest_state,
            report_state=report_state,
        ),
        "warnings": warnings,
        "warning_count": len(warnings),
        "artifacts": artifacts,
        "artifacts_present": any(artifact["present"] for artifact in artifacts),
        "artifact_count": len(artifacts),
        "missing_artifact_count": sum(
            1 for artifact in artifacts if not artifact["present"]
        ),
    }


def _read_json_document(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid"

    if not isinstance(payload, dict):
        return None, "invalid"
    return payload, "present"


def _run_id(
    run_root: Path,
    manifest: Mapping[str, Any] | None,
    report: Mapping[str, Any] | None,
) -> str:
    for payload in (manifest, report):
        if payload and payload.get("run_id"):
            return str(payload["run_id"])
    return run_root.name


def _input_model(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    input_info = manifest.get("input") if manifest else None
    if not isinstance(input_info, Mapping):
        return {
            "kind": "unknown",
            "stored_path": None,
            "source_path": None,
            "artifact_kind": None,
        }

    return {
        "kind": str(input_info.get("kind", "unknown")),
        "stored_path": _optional_string(input_info.get("stored_path")),
        "source_path": _optional_string(input_info.get("source_path")),
        "artifact_kind": _optional_string(input_info.get("artifact_kind")),
    }


def _stage_models(
    *,
    manifest: Mapping[str, Any] | None,
    report: Mapping[str, Any] | None,
    run_root: Path,
) -> list[dict[str, Any]]:
    report_stages = _as_list(report.get("stages")) if report else []
    if report_stages:
        return [
            _stage_from_report(stage, run_root=run_root)
            for stage in report_stages
            if isinstance(stage, Mapping)
        ]

    manifest_stages = manifest.get("stages") if manifest else None
    if isinstance(manifest_stages, Mapping):
        return [
            {
                "name": str(name),
                "status": "unknown",
                "message": "",
                "directory": _optional_string(dirname),
                "artifacts": [],
                "artifacts_present": False,
                "artifact_count": 0,
                "missing_artifact_count": 0,
            }
            for name, dirname in manifest_stages.items()
        ]
    return []


def _stage_from_report(stage: Mapping[str, Any], *, run_root: Path) -> dict[str, Any]:
    artifacts = _artifact_models(_as_list(stage.get("artifacts")), run_root=run_root)
    return {
        "name": str(stage.get("stage", "unknown")),
        "status": str(stage.get("status", "unknown")),
        "message": str(stage.get("message", "")),
        "artifacts": artifacts,
        "artifacts_present": any(artifact["present"] for artifact in artifacts),
        "artifact_count": len(artifacts),
        "missing_artifact_count": sum(
            1 for artifact in artifacts if not artifact["present"]
        ),
    }


def _artifact_models(
    artifacts: list[Any],
    *,
    run_root: Path,
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue

        path_value = artifact.get("path")
        resolved_path = _resolve_run_path(run_root, path_value)
        models.append(
            {
                "kind": str(artifact.get("kind", "unknown")),
                "label": str(artifact.get("label", "")),
                "path": _optional_string(path_value),
                "absolute_path": str(resolved_path) if resolved_path else None,
                "present": resolved_path.exists() if resolved_path else False,
            }
        )
    return models


def _report_artifacts(report: Mapping[str, Any] | None) -> list[Any]:
    if not report:
        return []
    artifacts = _as_list(report.get("artifacts"))
    if artifacts:
        return artifacts

    stage_artifacts: list[Any] = []
    for stage in _as_list(report.get("stages")):
        if isinstance(stage, Mapping):
            stage_artifacts.extend(_as_list(stage.get("artifacts")))
    return stage_artifacts


def _warning_items(report: Mapping[str, Any] | None) -> list[str]:
    if not report:
        return []
    return [str(warning) for warning in _as_list(report.get("warnings"))]


def _progress_model(
    stages: list[dict[str, Any]],
    *,
    manifest_state: str,
    report_state: str,
) -> dict[str, Any]:
    total = len(stages)
    failed = _count_status(stages, "failed")
    running = _count_status(stages, "running")
    complete = sum(
        1 for stage in stages if stage["status"] in FINISHED_STAGE_STATUSES
    )
    pending = sum(
        1
        for stage in stages
        if stage["status"] in PENDING_STAGE_STATUSES
        or stage["status"] not in FINISHED_STAGE_STATUSES | {"running"}
    )

    return {
        "state": _progress_state(
            stages,
            manifest_state=manifest_state,
            report_state=report_state,
            failed=failed,
            running=running,
            pending=pending,
        ),
        "total": total,
        "complete": complete,
        "failed": failed,
        "running": running,
        "pending": pending,
        "percent": round((complete / total) * 100) if total else 0,
    }


def _progress_state(
    stages: list[dict[str, Any]],
    *,
    manifest_state: str,
    report_state: str,
    failed: int,
    running: int,
    pending: int,
) -> str:
    if manifest_state == "missing":
        return "missing_manifest"
    if manifest_state == "invalid":
        return "invalid_manifest"
    if report_state == "missing":
        return "missing_report"
    if report_state == "invalid":
        return "invalid_report"
    if failed:
        return "failed"
    if running:
        return "running"
    if pending:
        return "in_progress"
    if stages:
        return "succeeded"
    return "unknown"


def _count_status(stages: list[dict[str, Any]], status: str) -> int:
    return sum(1 for stage in stages if stage["status"] == status)


def _file_presence(path: Path, *, run_root: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "relative_path": _relative_to_run(path, run_root=run_root),
        "present": path.exists(),
    }


def _resolve_run_path(run_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None

    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return run_root / path


def _relative_to_run(path: Path, *, run_root: Path) -> str:
    try:
        return path.resolve().relative_to(run_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = ["build_run_status"]
