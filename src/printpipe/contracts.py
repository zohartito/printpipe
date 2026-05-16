"""Shared contracts used across PrintPipe pipeline modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class InputKind(str, Enum):
    IMAGE = "image"
    GIF = "gif"
    VIDEO = "video"
    MESH = "mesh"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactKind(str, Enum):
    ORIGINAL_INPUT = "original_input"
    CLEANED_FRAME = "cleaned_frame"
    GENERATED_MESH = "generated_mesh"
    REPAIRED_MESH = "repaired_mesh"
    ORIENTED_MESH = "oriented_mesh"
    PROFILE_JSON = "profile_json"
    THREEMF = "3mf"
    SLICE_LOG = "slice_log"
    PREVIEW = "preview"
    REPORT = "report"


@dataclass(frozen=True)
class MeshStats:
    vertices: int
    faces: int
    watertight: bool
    euler_number: int | None = None
    boundary_edges: int | None = None
    non_manifold_edges: int | None = None
    bounds_mm: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    path: Path
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageReceipt:
    stage: str
    status: StageStatus
    message: str
    artifacts: tuple[Artifact, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

