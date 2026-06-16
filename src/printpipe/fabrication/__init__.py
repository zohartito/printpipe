"""Fabrication-verification contract and geometry helpers."""

from __future__ import annotations

from printpipe.fabrication.report import (
    Check,
    Dimension,
    ExportResult,
    FabricationReport,
    OrientationCandidate,
    PackingResult,
    PartResult,
    Provenance,
    Status,
    Target,
)
from printpipe.fabrication.verification import (
    pack,
    score_orientations,
    thicken_to_solids,
    validate,
)

__all__ = [
    "Check",
    "Dimension",
    "ExportResult",
    "FabricationReport",
    "OrientationCandidate",
    "PackingResult",
    "PartResult",
    "Provenance",
    "Status",
    "Target",
    "pack",
    "score_orientations",
    "thicken_to_solids",
    "validate",
]
