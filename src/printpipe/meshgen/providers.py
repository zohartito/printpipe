"""Provider implementations and registry helpers for mesh generation."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

from printpipe.contracts import Artifact, ArtifactKind, InputKind, StageStatus
from printpipe.runs.paths import RunLayout

from .contracts import (
    DeleteResult,
    MeshGenCapabilities,
    MeshGenCost,
    MeshGenError,
    MeshGenEstimate,
    MeshGenProvider,
    MeshGenRequest,
    MeshGenResult,
    MeshGenTiming,
    ProviderHealth,
)


MESH_SUFFIXES = {".stl", ".glb", ".gltf", ".obj", ".3mf"}
HUNYUAN3D_COMMAND_ENV = "PRINTPIPE_HUNYUAN3D_COMMAND"
MEDIA_MESHGEN_COMMAND_ENV = "PRINTPIPE_MEDIA_MESHGEN_COMMAND"
MEDIA_MESHGEN_INPUT_KINDS = (InputKind.IMAGE, InputKind.GIF, InputKind.VIDEO)
MEDIA_MESHGEN_UNAVAILABLE_MESSAGE = (
    "No live image/GIF/video meshgen provider is configured."
)
ProviderRegistry = MutableMapping[str, MeshGenProvider]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duration(started_at: float) -> float:
    return max(0.0, time.perf_counter() - started_at)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _cost_dict(cost: MeshGenCost) -> dict[str, Any]:
    return {key: value for key, value in asdict(cost).items() if value is not None}


def _timing_dict(timing: MeshGenTiming) -> dict[str, Any]:
    return {key: value for key, value in asdict(timing).items() if value is not None}


def _error_dict(error: MeshGenError | None) -> dict[str, Any] | None:
    if error is None:
        return None
    return {
        "category": error.category,
        "message": error.message,
        "retryable": error.retryable,
        "vendor_message": error.vendor_message,
    }


def _artifact_dict(artifact: Artifact | None, run: RunLayout) -> dict[str, Any] | None:
    if artifact is None:
        return None
    return {
        "kind": artifact.kind.value,
        "path": _safe_relative(artifact.path, run.root),
        "label": artifact.label,
        "metadata": artifact.metadata,
    }


def _result_record(result: MeshGenResult, run: RunLayout) -> dict[str, Any]:
    output_paths = {
        "raw_output_path": (
            _safe_relative(result.raw_output_path, run.root)
            if result.raw_output_path is not None
            else None
        ),
        "normalized_mesh_path": (
            _safe_relative(result.normalized_mesh_path, run.root)
            if result.normalized_mesh_path is not None
            else None
        ),
        "preview_path": (
            _safe_relative(result.preview_path, run.root)
            if result.preview_path is not None
            else None
        ),
    }
    return {
        "schema_version": 1,
        "run_id": run.run_id,
        "provider_id": result.provider_id,
        "status": result.status.value,
        "attempt_count": result.attempt_count,
        "model_id": result.model_id,
        "model_version": result.model_version,
        "api_endpoint": result.api_endpoint,
        "remote_job_id": result.remote_job_id,
        "remote_request_id": result.remote_request_id,
        "timing": _timing_dict(result.timing),
        "cost": _cost_dict(result.cost),
        "input_hashes": result.input_hashes,
        "output_hashes": result.output_hashes,
        "output_paths": output_paths,
        "artifact": _artifact_dict(result.artifact, run),
        "mesh_stats": asdict(result.mesh_stats) if result.mesh_stats is not None else None,
        "error": _error_dict(result.error),
        "fallback_from": result.fallback_from,
        "fallback_reason": result.fallback_reason,
        "remote_artifacts_deleted": result.remote_artifacts_deleted,
    }


def write_provider_receipts(result: MeshGenResult, run: RunLayout) -> None:
    run.meshgen_dir.mkdir(parents=True, exist_ok=True)
    record = _result_record(result, run)
    attempts_path = run.meshgen_dir / "attempts.jsonl"
    summary_path = run.meshgen_dir / "summary.json"

    with attempts_path.open("a", encoding="utf-8") as attempts_file:
        attempts_file.write(json.dumps(record, sort_keys=True) + "\n")

    summary_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ExistingMeshProvider:
    provider_id = "existing_mesh"
    display_name = "Existing mesh import"
    adapter_version = "0.1.0"
    capabilities = MeshGenCapabilities(
        input_kinds=(InputKind.MESH,),
        output_formats=("stl", "glb", "gltf", "obj", "3mf"),
        supports_cloud=False,
        supports_local=True,
        supports_remote_delete=False,
    )

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate:
        return MeshGenEstimate(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            estimated_seconds=0.0,
            message="Existing mesh import is local and free.",
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            message="Existing mesh import is available.",
            checked_at=utc_now(),
        )

    def generate(self, request: MeshGenRequest, run: RunLayout) -> MeshGenResult:
        started_perf = time.perf_counter()
        started_at = utc_now()

        failure = self._validate_request(request)
        if failure is not None:
            result = self._failure_result(
                category="invalid_request",
                message=failure,
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
            )
            write_provider_receipts(result, run)
            return result

        source_path = request.source_paths[0]
        destination = self._destination_path(source_path, run.meshgen_dir)
        shutil.copy2(source_path, destination)
        source_hash = sha256_file(source_path)
        output_hash = sha256_file(destination)
        ended_at = utc_now()
        artifact = Artifact(
            kind=ArtifactKind.GENERATED_MESH,
            path=destination,
            label="Imported mesh",
            metadata={
                "provider_id": self.provider_id,
                "source_path": str(source_path),
                "sha256": output_hash,
            },
        )
        result = MeshGenResult(
            status=StageStatus.SUCCEEDED,
            provider_id=self.provider_id,
            model_id="existing_mesh_import",
            timing=MeshGenTiming(
                started_at=started_at,
                ended_at=ended_at,
                queue_seconds=0.0,
                run_seconds=_duration(started_perf),
                download_seconds=0.0,
                wall_seconds=_duration(started_perf),
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            attempt_count=1,
            raw_output_path=destination,
            normalized_mesh_path=destination,
            artifact=artifact,
            input_hashes={str(source_path): source_hash},
            output_hashes={str(destination): output_hash},
        )
        write_provider_receipts(result, run)
        return result

    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult:
        return DeleteResult(
            status=StageStatus.SKIPPED,
            message="Existing mesh import creates no remote artifacts.",
        )

    def _validate_request(self, request: MeshGenRequest) -> str | None:
        if request.input_kind != InputKind.MESH:
            return "existing_mesh provider only accepts mesh input"
        if not request.source_paths:
            return "existing_mesh provider requires a source mesh path"
        source_path = request.source_paths[0]
        if not source_path.exists():
            return f"source mesh does not exist: {source_path}"
        if source_path.suffix.lower() not in MESH_SUFFIXES:
            return f"unsupported mesh suffix: {source_path.suffix or source_path.name}"
        return None

    def _destination_path(self, source_path: Path, meshgen_dir: Path) -> Path:
        meshgen_dir.mkdir(parents=True, exist_ok=True)
        destination = meshgen_dir / source_path.name
        if not destination.exists():
            return destination

        stem = source_path.stem
        suffix = source_path.suffix
        index = 2
        while True:
            candidate = meshgen_dir / f"{stem}-{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _failure_result(
        self,
        *,
        category: str,
        message: str,
        retryable: bool,
        started_at: str,
        wall_seconds: float,
    ) -> MeshGenResult:
        return MeshGenResult(
            status=StageStatus.FAILED,
            provider_id=self.provider_id,
            timing=MeshGenTiming(
                started_at=started_at,
                ended_at=utc_now(),
                wall_seconds=wall_seconds,
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            attempt_count=1,
            error=MeshGenError(category=category, message=message, retryable=retryable),
        )


class Hunyuan3DProvider:
    provider_id = "hunyuan3d"
    display_name = "Hunyuan3D local command"
    adapter_version = "0.1.0"
    model_id = "hunyuan3d-local-command"
    command_env = HUNYUAN3D_COMMAND_ENV
    capabilities = MeshGenCapabilities(
        input_kinds=(InputKind.IMAGE, InputKind.GIF, InputKind.VIDEO),
        output_formats=("glb", "stl", "obj"),
        supports_cloud=False,
        supports_local=True,
        supports_remote_delete=False,
    )

    def __init__(
        self,
        command: str | Path | Sequence[str | Path] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.command = self._configured_command(command)
        self._runner = runner or self._run_subprocess

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate:
        if not self.command:
            return MeshGenEstimate(
                provider_id=self.provider_id,
                status=StageStatus.SKIPPED,
                cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
                estimated_seconds=None,
                message=(
                    f"{self.display_name} is not configured; set "
                    f"{self.command_env} or pass a command path."
                ),
            )

        return MeshGenEstimate(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            estimated_seconds=None,
            message=f"{self.display_name} is configured; adapter cost is local/free.",
        )

    def healthcheck(self) -> ProviderHealth:
        if not self.command:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=StageStatus.SKIPPED,
                message=(
                    f"{self.display_name} is not configured. Set "
                    f"{self.command_env} to enable this provider."
                ),
                checked_at=utc_now(),
            )

        return ProviderHealth(
            provider_id=self.provider_id,
            status=StageStatus.SUCCEEDED,
            message=f"{self.display_name} is configured: {self.command[0]}",
            checked_at=utc_now(),
        )

    def generate(self, request: MeshGenRequest, run: RunLayout) -> MeshGenResult:
        started_perf = time.perf_counter()
        started_at = utc_now()

        if not self.command:
            result = self._failure_result(
                category="provider_unavailable",
                message=(
                    f"{self.display_name} is not configured; set "
                    f"{self.command_env} or pass a command path."
                ),
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
            )
            write_provider_receipts(result, run)
            return result

        failure = self._validate_request(request)
        if failure is not None:
            result = self._failure_result(
                category="invalid_request",
                message=failure,
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
            )
            write_provider_receipts(result, run)
            return result

        output_format = self._select_output_format(request)
        if output_format is None:
            result = self._failure_result(
                category="invalid_request",
                message=(
                    f"{self.display_name} cannot produce requested output formats: "
                    f"{', '.join(request.output_formats)}"
                ),
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
            )
            write_provider_receipts(result, run)
            return result

        destination = self._destination_path(run.meshgen_dir, output_format)
        argv = self._build_command(request, destination, output_format)
        try:
            completed = self._runner(argv, timeout_seconds=request.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            result = self._failure_result(
                category="provider_timeout",
                message=f"{self.display_name} timed out after {request.timeout_seconds}s.",
                retryable=True,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
                vendor_message=str(exc),
            )
            write_provider_receipts(result, run)
            return result
        except OSError as exc:
            result = self._failure_result(
                category="provider_command_error",
                message=f"{self.display_name} could not be started: {exc}",
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
                vendor_message=str(exc),
            )
            write_provider_receipts(result, run)
            return result

        if completed.returncode != 0:
            result = self._failure_result(
                category="provider_command_failed",
                message=f"{self.display_name} exited with code {completed.returncode}.",
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
                vendor_message=self._vendor_message(completed),
            )
            write_provider_receipts(result, run)
            return result

        source_output = self._resolve_output_path(completed, destination)
        if source_output is None:
            result = self._failure_result(
                category="provider_output_missing",
                message=(
                    f"{self.display_name} succeeded but did not create the requested "
                    "mesh output or report an output_path."
                ),
                retryable=False,
                started_at=started_at,
                wall_seconds=_duration(started_perf),
                vendor_message=self._vendor_message(completed),
            )
            write_provider_receipts(result, run)
            return result

        if source_output.resolve() != destination.resolve():
            shutil.copy2(source_output, destination)

        output_hash = sha256_file(destination)
        ended_at = utc_now()
        timing_seconds = _duration(started_perf)
        input_paths = request.source_paths + request.reference_images
        artifact = Artifact(
            kind=ArtifactKind.GENERATED_MESH,
            path=destination,
            label=f"Generated mesh from {self.display_name}",
            metadata={
                "provider_id": self.provider_id,
                "command": argv,
                "source_output_path": str(source_output),
                "sha256": output_hash,
            },
        )
        result = MeshGenResult(
            status=StageStatus.SUCCEEDED,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_version=request.provider_params.get("model_version"),
            timing=MeshGenTiming(
                started_at=started_at,
                ended_at=ended_at,
                queue_seconds=0.0,
                run_seconds=timing_seconds,
                download_seconds=0.0,
                wall_seconds=timing_seconds,
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            attempt_count=1,
            raw_output_path=destination,
            normalized_mesh_path=destination,
            artifact=artifact,
            input_hashes={str(path): sha256_file(path) for path in input_paths},
            output_hashes={str(destination): output_hash},
        )
        write_provider_receipts(result, run)
        return result

    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult:
        return DeleteResult(
            status=StageStatus.SKIPPED,
            message=f"{self.display_name} creates no remote artifacts.",
        )

    def _configured_command(
        self,
        command: str | Path | Sequence[str | Path] | None,
    ) -> tuple[str, ...]:
        if command is None:
            env_value = os.environ.get(self.command_env, "").strip()
            return tuple(shlex.split(env_value)) if env_value else ()
        if isinstance(command, Path):
            return (str(command),)
        if isinstance(command, str):
            return tuple(shlex.split(command))
        return tuple(str(part) for part in command if str(part))

    def _run_subprocess(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )

    def _validate_request(self, request: MeshGenRequest) -> str | None:
        if request.input_kind not in self.capabilities.input_kinds:
            return f"{self.provider_id} provider only accepts image, gif, or video input"
        if not request.source_paths:
            return "hunyuan3d provider requires at least one source reference path"
        missing = [
            path
            for path in request.source_paths + request.reference_images
            if not path.exists()
        ]
        if missing:
            return f"source reference does not exist: {missing[0]}"
        return None

    def _select_output_format(self, request: MeshGenRequest) -> str | None:
        requested = tuple(format_name.lower().lstrip(".") for format_name in request.output_formats)
        for format_name in requested:
            if format_name in self.capabilities.output_formats:
                return format_name
        return None

    def _destination_path(self, meshgen_dir: Path, output_format: str) -> Path:
        meshgen_dir.mkdir(parents=True, exist_ok=True)
        destination = meshgen_dir / f"{self.provider_id}.{output_format}"
        if not destination.exists():
            return destination

        index = 2
        while True:
            candidate = meshgen_dir / f"{self.provider_id}-{index}.{output_format}"
            if not candidate.exists():
                return candidate
            index += 1

    def _build_command(
        self,
        request: MeshGenRequest,
        destination: Path,
        output_format: str,
    ) -> tuple[str, ...]:
        argv = [
            *self.command,
            "--input-kind",
            request.input_kind.value,
            "--output",
            str(destination),
            "--output-format",
            output_format,
            "--target-use",
            request.target_use,
            "--quality",
            request.quality,
        ]
        for source_path in request.source_paths:
            argv.extend(("--source", str(source_path)))
        for reference_image in request.reference_images:
            argv.extend(("--reference-image", str(reference_image)))
        if request.prompt_hint:
            argv.extend(("--prompt", request.prompt_hint))
        if request.seed is not None:
            argv.extend(("--seed", str(request.seed)))
        if request.provider_params:
            argv.extend(("--params-json", json.dumps(request.provider_params, sort_keys=True)))
        return tuple(argv)

    def _resolve_output_path(
        self,
        completed: subprocess.CompletedProcess[str],
        destination: Path,
    ) -> Path | None:
        if destination.exists():
            return destination

        stdout = (completed.stdout or "").strip()
        if not stdout:
            return None

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            for line in reversed(stdout.splitlines()):
                candidate = Path(line.strip())
                if candidate.exists() and candidate.suffix.lower() in MESH_SUFFIXES:
                    return candidate
            return None

        if not isinstance(payload, dict):
            return None
        output_path = payload.get("output_path") or payload.get("mesh_path") or payload.get("path")
        if not isinstance(output_path, str):
            return None
        candidate = Path(output_path)
        if candidate.exists() and candidate.suffix.lower() in MESH_SUFFIXES:
            return candidate
        return None

    def _vendor_message(self, completed: subprocess.CompletedProcess[str]) -> str | None:
        parts = []
        if completed.stdout:
            parts.append(f"stdout: {completed.stdout.strip()}")
        if completed.stderr:
            parts.append(f"stderr: {completed.stderr.strip()}")
        if not parts:
            return None
        return "\n".join(parts)[:4000]

    def _failure_result(
        self,
        *,
        category: str,
        message: str,
        retryable: bool,
        started_at: str,
        wall_seconds: float,
        vendor_message: str | None = None,
    ) -> MeshGenResult:
        return MeshGenResult(
            status=StageStatus.FAILED,
            provider_id=self.provider_id,
            model_id=self.model_id,
            timing=MeshGenTiming(
                started_at=started_at,
                ended_at=utc_now(),
                wall_seconds=wall_seconds,
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=False),
            attempt_count=1,
            error=MeshGenError(
                category=category,
                message=message,
                retryable=retryable,
                vendor_message=vendor_message,
            ),
        )


class MediaCommandMeshProvider(Hunyuan3DProvider):
    provider_id = "media_command"
    display_name = "Generic media meshgen command"
    model_id = "generic-media-command"
    command_env = MEDIA_MESHGEN_COMMAND_ENV


class PlaceholderMeshProvider:
    adapter_version = "0.1.0"

    def __init__(self, provider_id: str, display_name: str) -> None:
        self.provider_id = provider_id
        self.display_name = display_name
        self.capabilities = MeshGenCapabilities(
            input_kinds=(InputKind.IMAGE, InputKind.GIF, InputKind.VIDEO),
            supports_cloud=True,
            supports_local=False,
            supports_remote_delete=False,
        )

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate:
        return MeshGenEstimate(
            provider_id=self.provider_id,
            status=StageStatus.SKIPPED,
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=True),
            estimated_seconds=None,
            message=f"{self.display_name} provider is a placeholder; no live calls are made.",
        )

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=StageStatus.SKIPPED,
            message=f"{self.display_name} provider is not implemented yet.",
            checked_at=utc_now(),
        )

    def generate(self, request: MeshGenRequest, run: RunLayout) -> MeshGenResult:
        started_perf = time.perf_counter()
        result = MeshGenResult(
            status=StageStatus.FAILED,
            provider_id=self.provider_id,
            timing=MeshGenTiming(
                started_at=utc_now(),
                ended_at=utc_now(),
                wall_seconds=_duration(started_perf),
            ),
            cost=MeshGenCost(currency="USD", amount=0.0, estimated=True),
            attempt_count=1,
            error=MeshGenError(
                category="provider_unavailable",
                message=f"{self.display_name} provider is a placeholder; no live calls are made.",
                retryable=False,
            ),
        )
        write_provider_receipts(result, run)
        return result

    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult:
        return DeleteResult(
            status=StageStatus.SKIPPED,
            message=f"{self.display_name} placeholder has no remote artifacts.",
        )


def register_provider(
    provider: MeshGenProvider,
    registry: ProviderRegistry | None = None,
) -> ProviderRegistry:
    actual_registry: ProviderRegistry = registry if registry is not None else default_registry()
    actual_registry[provider.provider_id] = provider
    return actual_registry


def get_provider(provider_id: str, registry: ProviderRegistry | None = None) -> MeshGenProvider:
    actual_registry = registry if registry is not None else default_registry()
    try:
        return actual_registry[provider_id]
    except KeyError as exc:
        available = ", ".join(sorted(actual_registry)) or "none"
        raise KeyError(f"unknown meshgen provider '{provider_id}' (available: {available})") from exc


def available_provider_ids(registry: ProviderRegistry | None = None) -> tuple[str, ...]:
    actual_registry = registry if registry is not None else default_registry()
    return tuple(sorted(actual_registry))


def build_media_meshgen_readiness(
    *,
    registry: ProviderRegistry | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    actual_registry = (
        registry
        if registry is not None
        else _default_readiness_registry(env=env)
    )
    provider_summaries: list[dict[str, Any]] = []
    live_media_provider_count = 0
    for provider in actual_registry.values():
        health = provider.healthcheck()
        input_kinds = tuple(kind.value for kind in provider.capabilities.input_kinds)
        supports_media = any(
            input_kind in provider.capabilities.input_kinds
            for input_kind in MEDIA_MESHGEN_INPUT_KINDS
        )
        if supports_media and health.status == StageStatus.SUCCEEDED:
            live_media_provider_count += 1
        provider_summaries.append(
            {
                "provider_id": provider.provider_id,
                "display_name": provider.display_name,
                "status": health.status.value,
                "message": health.message,
                "input_kinds": list(input_kinds),
                "supports_media": supports_media,
                "supports_cloud": provider.capabilities.supports_cloud,
                "supports_local": provider.capabilities.supports_local,
            }
        )

    ready = live_media_provider_count > 0
    return {
        "overall_status": "ready" if ready else "action_required",
        "live_media_provider_count": live_media_provider_count,
        "required_input_kinds": [kind.value for kind in MEDIA_MESHGEN_INPUT_KINDS],
        "message": (
            "At least one live image/GIF/video meshgen provider is configured."
            if ready
            else MEDIA_MESHGEN_UNAVAILABLE_MESSAGE
        ),
        "action": (
            "No action needed."
            if ready
            else (
                f"Set {MEDIA_MESHGEN_COMMAND_ENV}, set {HUNYUAN3D_COMMAND_ENV}, "
                "or configure a hosted mesh provider."
            )
        ),
        "providers": provider_summaries,
    }


def default_registry() -> dict[str, MeshGenProvider]:
    registry: dict[str, MeshGenProvider] = {}
    register_provider(ExistingMeshProvider(), registry)
    register_provider(Hunyuan3DProvider(), registry)
    register_provider(MediaCommandMeshProvider(), registry)
    register_provider(PlaceholderMeshProvider("replicate", "Replicate"), registry)
    register_provider(PlaceholderMeshProvider("meshy", "Meshy"), registry)
    register_provider(PlaceholderMeshProvider("rodin", "Rodin"), registry)
    return registry


def _default_readiness_registry(
    *,
    env: Mapping[str, str] | None,
) -> dict[str, MeshGenProvider]:
    hunyuan_command = None
    media_command = None
    if env is not None:
        hunyuan_command = env.get(HUNYUAN3D_COMMAND_ENV, "")
        media_command = env.get(MEDIA_MESHGEN_COMMAND_ENV, "")
    registry: dict[str, MeshGenProvider] = {}
    register_provider(ExistingMeshProvider(), registry)
    register_provider(Hunyuan3DProvider(command=hunyuan_command), registry)
    register_provider(MediaCommandMeshProvider(command=media_command), registry)
    register_provider(PlaceholderMeshProvider("replicate", "Replicate"), registry)
    register_provider(PlaceholderMeshProvider("meshy", "Meshy"), registry)
    register_provider(PlaceholderMeshProvider("rodin", "Rodin"), registry)
    return registry


def generate_with_retries(
    provider: MeshGenProvider,
    request: MeshGenRequest,
    run: RunLayout,
) -> MeshGenResult:
    max_attempts = max(1, request.max_attempts)
    last_result: MeshGenResult | None = None

    for attempt in range(1, max_attempts + 1):
        result = provider.generate(request, run)
        result = replace(result, attempt_count=attempt)
        if result.status == StageStatus.SUCCEEDED:
            return result
        last_result = result
        if result.error is None or not result.error.retryable:
            return result

    if last_result is None:
        raise RuntimeError("meshgen retry loop did not run")
    return replace(last_result, attempt_count=max_attempts)
