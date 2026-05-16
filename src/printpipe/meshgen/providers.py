"""Provider implementations and registry helpers for mesh generation."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
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
ProviderRegistry = MutableMapping[str, MeshGenProvider]


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


def default_registry() -> dict[str, MeshGenProvider]:
    registry: dict[str, MeshGenProvider] = {}
    register_provider(ExistingMeshProvider(), registry)
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
