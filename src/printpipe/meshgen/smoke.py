"""Smoke-test helpers for configured media meshgen command adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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
) -> dict[str, Any]:
    """Run configured media meshgen only, writing a narrow smoke receipt."""

    input_kind = classify_input_path(input_path)
    if input_kind not in MEDIA_INPUT_KINDS:
        raise ValueError("media meshgen smoke requires image, GIF, or video input")

    layout = create_run(input_path, runs_dir)
    input_result = prepare_input(layout.original_input, layout.frames_dir)
    reference_paths = tuple(Path(artifact.path) for artifact in input_result.selected_references)
    provider = _smoke_provider(command=command)
    request = MeshGenRequest(
        input_kind=input_result.kind,
        source_paths=reference_paths,
        reference_images=reference_paths,
        output_formats=(output_format,),
        prompt_hint=prompt,
        max_attempts=1,
        provider_params={"smoke": True, "original_input": str(layout.original_input)},
    )
    result = generate_with_retries(provider, request, layout)
    return _write_smoke_receipt(layout, input_kind=input_result.kind, result=result)


def _smoke_provider(*, command: str | None) -> MeshGenProvider:
    if command:
        return MediaCommandMeshProvider(command=command)
    if os.environ.get(MEDIA_MESHGEN_COMMAND_ENV, "").strip():
        return MediaCommandMeshProvider()
    if os.environ.get(HUNYUAN3D_COMMAND_ENV, "").strip():
        return Hunyuan3DProvider()
    return MediaCommandMeshProvider()


def _write_smoke_receipt(
    layout: RunLayout,
    *,
    input_kind: InputKind,
    result: MeshGenResult,
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
