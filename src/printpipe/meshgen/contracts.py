"""Contracts for PrintPipe mesh generation providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from printpipe.contracts import Artifact, InputKind, MeshStats, StageStatus
from printpipe.runs.paths import RunLayout


DEFAULT_OUTPUT_FORMATS = ("glb", "stl", "obj")


@dataclass(frozen=True)
class MeshGenCapabilities:
    input_kinds: tuple[InputKind, ...]
    output_formats: tuple[str, ...] = DEFAULT_OUTPUT_FORMATS
    supports_cloud: bool = False
    supports_local: bool = True
    supports_remote_delete: bool = False


@dataclass(frozen=True)
class MeshGenCost:
    currency: str = "USD"
    amount: float | None = None
    credits: float | None = None
    billable_units: float | None = None
    estimated: bool = True


@dataclass(frozen=True)
class MeshGenTiming:
    started_at: str | None = None
    ended_at: str | None = None
    queue_seconds: float | None = None
    run_seconds: float | None = None
    download_seconds: float | None = None
    wall_seconds: float = 0.0


@dataclass(frozen=True)
class MeshGenError:
    category: str
    message: str
    retryable: bool
    vendor_message: str | None = None


@dataclass(frozen=True)
class MeshGenRequest:
    input_kind: InputKind
    source_paths: tuple[Path, ...]
    reference_images: tuple[Path, ...] = ()
    prompt_hint: str | None = None
    target_use: str = "3d_printing"
    output_formats: tuple[str, ...] = DEFAULT_OUTPUT_FORMATS
    quality: str = "standard"
    seed: int | None = None
    provider_params: dict[str, Any] = field(default_factory=dict)
    privacy_mode: str = "local_only"
    max_attempts: int = 2
    timeout_seconds: int = 1800
    budget_usd: float | None = None
    budget_credits: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_paths", tuple(Path(path) for path in self.source_paths))
        object.__setattr__(
            self,
            "reference_images",
            tuple(Path(path) for path in self.reference_images),
        )
        object.__setattr__(self, "output_formats", tuple(self.output_formats))


@dataclass(frozen=True)
class MeshGenEstimate:
    provider_id: str
    status: StageStatus
    cost: MeshGenCost
    estimated_seconds: float | None = None
    message: str = ""


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    status: StageStatus
    message: str
    checked_at: str


@dataclass(frozen=True)
class DeleteResult:
    status: StageStatus
    message: str


@dataclass(frozen=True)
class MeshGenResult:
    status: StageStatus
    provider_id: str
    timing: MeshGenTiming
    cost: MeshGenCost
    attempt_count: int = 1
    model_id: str | None = None
    model_version: str | None = None
    api_endpoint: str | None = None
    attempt_id: str | None = None
    remote_job_id: str | None = None
    remote_request_id: str | None = None
    raw_output_path: Path | None = None
    normalized_mesh_path: Path | None = None
    preview_path: Path | None = None
    artifact: Artifact | None = None
    input_hashes: dict[str, str] = field(default_factory=dict)
    output_hashes: dict[str, str] = field(default_factory=dict)
    mesh_stats: MeshStats | None = None
    error: MeshGenError | None = None
    fallback_from: str | None = None
    fallback_reason: str | None = None
    remote_artifacts_deleted: str = "unsupported"


@runtime_checkable
class MeshGenProvider(Protocol):
    provider_id: str
    display_name: str
    capabilities: MeshGenCapabilities

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate:
        """Return a local estimate without starting provider work."""

    def generate(self, request: MeshGenRequest, run: RunLayout) -> MeshGenResult:
        """Generate or import one raw mesh into the run meshgen directory."""

    def healthcheck(self) -> ProviderHealth:
        """Return provider availability without doing billable work."""

    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult:
        """Delete remote artifacts when the provider supports cleanup."""
