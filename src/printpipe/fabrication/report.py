"""Fabrication-verification report contract.

These dataclasses are the shared seam between geometry verification and the
pipeline/UI layers. Keep them small and JSON-friendly; geometry objects stay at
the function boundary, not inside the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Provenance(str, Enum):
    DATASHEET = "datasheet"
    MEASURED = "measured"
    SCANNED = "scanned"
    ASSUMED = "assumed"


class Status(str, Enum):
    PASS = "pass"
    FLAG = "flag"
    FAIL = "fail"


class Target(str, Enum):
    PRINT = "print"
    LASER = "laser"


@dataclass(frozen=True)
class Dimension:
    name: str
    value_mm: float
    provenance: Provenance
    fit_critical: bool = False
    confidence: float = 1.0
    source: str = ""


@dataclass
class PartResult:
    id: str
    source_faces: int
    thicken_dir_mm: float | None
    solid: bool
    valid: bool
    failure_reason: str | None = None


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    depends_on_assumed_dim: str | None = None


@dataclass
class OrientationCandidate:
    name: str
    support_volume_mm3: float
    stability: float
    score: float


@dataclass
class PackingResult:
    unit: str
    units_used: int
    layout: list[dict]
    efficiency: float
    unplaced: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    stl_paths: list[str] = field(default_factory=list)
    openable_3mf: str | None = None
    dxf_layers: list[str] = field(default_factory=list)
    scale: float = 1.0


@dataclass
class FabricationReport:
    units: str
    tolerance_mm: float
    wall_thickness_mm: float
    target: Target
    dimensions: list[Dimension]
    parts: list[PartResult]
    valid_solids: str
    printability: list[Check]
    orientation: OrientationCandidate | None
    packing: PackingResult | None
    exports: ExportResult
    agent_summary: str

    @property
    def ready_to_print(self) -> bool:
        if any(c.status == Status.FAIL for c in self.printability):
            return False
        if any(not p.valid for p in self.parts):
            return False
        if self.packing is not None and self.packing.unplaced:
            return False
        if any(d.provenance == Provenance.ASSUMED and d.fit_critical for d in self.dimensions):
            return False
        return True
