"""Smoke-test helpers for configured media meshgen command adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from printpipe.config import configured_media_meshgen_command, configured_media_meshgen_params
from printpipe.contracts import InputKind, StageStatus
from printpipe.inputs import classify_input_path, prepare_input
from printpipe.meshgen.contracts import MeshGenRequest, MeshGenResult, MeshGenProvider
from printpipe.meshgen.providers import (
    HUNYUAN3D_COMMAND_ENV,
    MEDIA_MESHGEN_COMMAND_ENV,
    Hunyuan3DProvider,
    MediaCommandMeshProvider,
    generate_with_retries,
)
from printpipe.runs import RunLayout, create_run


MEDIA_INPUT_KINDS = frozenset({InputKind.IMAGE, InputKind.GIF, InputKind.VIDEO})


def run_media_meshgen_smoke(
    input_path: Path,
    *,
    runs_dir: Path = Path("runs/media-meshgen-smoke"),
    command: str | None = None,
    output_format: str = "stl",
    prompt: str | None = None,
    config_cwd: Path | None = None,
) -> dict[str, Any]:
    """Run configured media meshgen only, writing a narrow smoke receipt."""

    input_kind = classify_input_path(input_path)
    if input_kind not in MEDIA_INPUT_KINDS:
        raise ValueError("media meshgen smoke requires image, GIF, or video input")

    layout = create_run(input_path, runs_dir)
    input_result = prepare_input(layout.original_input, layout.frames_dir)
    reference_paths = tuple(Path(artifact.path) for artifact in input_result.selected_references)
    provider = _smoke_provider(command=command, config_cwd=config_cwd)
    configured_command = _configured_smoke_command(
        command,
        config_cwd=config_cwd,
    )
    request = MeshGenRequest(
        input_kind=input_result.kind,
        source_paths=reference_paths,
        reference_images=reference_paths,
        output_formats=(output_format,),
        prompt_hint=prompt,
        max_attempts=1,
        provider_params={
            **_configured_smoke_params(config_cwd=config_cwd),
            "smoke": True,
            "original_input": str(layout.original_input),
        },
    )
    result = generate_with_retries(provider, request, layout)
    return _write_smoke_receipt(
        layout,
        input_kind=input_result.kind,
        result=result,
        command=configured_command,
    )


def _smoke_provider(
    *,
    command: str | None,
    config_cwd: Path | None,
) -> MeshGenProvider:
    if command:
        return MediaCommandMeshProvider(command=command)
    media_command = _configured_project_media_command(config_cwd=config_cwd)
    if media_command:
        return MediaCommandMeshProvider(command=media_command)
    if os.environ.get(HUNYUAN3D_COMMAND_ENV, "").strip():
        return Hunyuan3DProvider()
    return MediaCommandMeshProvider()


def _configured_smoke_command(
    command: str | None,
    *,
    config_cwd: Path | None,
) -> str:
    if command:
        return command.strip()
    media_command = _configured_project_media_command(config_cwd=config_cwd)
    if media_command:
        return media_command
    hunyuan_command = os.environ.get(HUNYUAN3D_COMMAND_ENV, "").strip()
    if hunyuan_command:
        return hunyuan_command
    return ""


def _configured_project_media_command(*, config_cwd: Path | None) -> str:
    if config_cwd is None:
        return configured_media_meshgen_command()
    env_command = os.environ.get(MEDIA_MESHGEN_COMMAND_ENV, "").strip()
    if env_command:
        return env_command
    return configured_media_meshgen_command(config_path=_project_config_path(config_cwd))


def _configured_smoke_params(*, config_cwd: Path | None) -> dict[str, Any]:
    if config_cwd is None:
        return configured_media_meshgen_params()
    return configured_media_meshgen_params(config_path=_project_config_path(config_cwd))


def _project_config_path(config_cwd: Path) -> Path:
    return config_cwd.expanduser() / ".printpipe" / "config.json"


def _write_smoke_receipt(
    layout: RunLayout,
    *,
    input_kind: InputKind,
    result: MeshGenResult,
    command: str,
) -> dict[str, Any]:
    smoke_path = layout.meshgen_dir / "smoke.json"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "run_id": layout.run_id,
        "run_root": str(layout.root),
        "input_kind": input_kind.value,
        "provider_id": result.provider_id,
        "status": result.status.value,
        "attempt_count": result.attempt_count,
        "summary_path": _relative(layout, layout.meshgen_dir / "summary.json"),
        "attempts_path": _relative(layout, layout.meshgen_dir / "attempts.jsonl"),
    }
    if command:
        payload["command"] = command
    if result.normalized_mesh_path is not None:
        payload["output_path"] = _relative(layout, result.normalized_mesh_path)
    if result.error is not None:
        payload["error"] = result.error.message
        payload["error_category"] = result.error.category
        payload["retryable"] = result.error.retryable
    smoke_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["smoke_path"] = _relative(layout, smoke_path)
    return payload


def _relative(layout: RunLayout, path: Path) -> str:
    try:
        return str(path.relative_to(layout.root))
    except ValueError:
        return str(path)


def smoke_exit_code(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == StageStatus.SUCCEEDED.value else 2


def build_media_meshgen_smoke_status(runs_dir: str | Path) -> dict[str, Any]:
    """Summarize successful media meshgen smoke receipts under a runs dir."""

    root = Path(runs_dir).expanduser().resolve()
    smoke_receipts: list[dict[str, Any]] = []
    successful: list[dict[str, Any]] = []
    if root.exists():
        for smoke_path in sorted(root.glob("**/20_meshgen/smoke.json")):
            receipt = _read_smoke_receipt(root, smoke_path)
            if receipt is None:
                continue
            smoke_receipts.append(receipt)
            if receipt["status"] == StageStatus.SUCCEEDED.value and receipt.get(
                "output_exists"
            ):
                successful.append(receipt)

    latest = successful[-1] if successful else None
    passed = latest is not None
    return {
        "schema_version": 1,
        "runs_dir": str(root),
        "overall_status": "passed" if passed else "missing",
        "smoke_receipt_count": len(smoke_receipts),
        "successful_smoke_count": len(successful),
        "failed_smoke_count": sum(
            1 for receipt in smoke_receipts if receipt["status"] != StageStatus.SUCCEEDED.value
        ),
        "latest_successful_smoke": latest,
        "message": (
            f"{len(successful)} successful media meshgen smoke receipt(s) found."
            if passed
            else "No successful media meshgen smoke receipt found."
        ),
        "action": (
            "No action needed."
            if passed
            else (
                "Run printpipe media-meshgen-smoke reference.png "
                f"--runs-dir {root}"
            )
        ),
    }


def _read_smoke_receipt(root: Path, smoke_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(smoke_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    run_root = smoke_path.parents[1]
    output_path = payload.get("output_path")
    output_exists = False
    if isinstance(output_path, str) and output_path:
        output_exists = (run_root / output_path).exists()
    return {
        "run_id": str(payload.get("run_id") or run_root.name),
        "run_root": str(run_root),
        "provider_id": str(payload.get("provider_id") or "unknown"),
        "status": str(payload.get("status") or "unknown"),
        "smoke_path": _relative_to(root, smoke_path),
        "output_path": output_path if isinstance(output_path, str) else None,
        "output_exists": output_exists,
        "command": payload.get("command") if isinstance(payload.get("command"), str) else "",
        "error": payload.get("error") if isinstance(payload.get("error"), str) else None,
    }


def _relative_to(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
