"""Fabrication-verification contract and geometry helpers."""

from __future__ import annotations

from printpipe.fabrication.pipeline import (
    FabricationModel,
    FabricationSettings,
    FitContext,
    check_fit,
    fabricate,
)
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
from printpipe.fabrication.serialize import (
    FABRICATION_REPORT_SCHEMA_VERSION,
    to_dict,
)
from printpipe.fabrication.verification import (
    pack,
    score_orientations,
    thicken_to_solids,
    validate,
)

__all__ = [
    "FABRICATION_REPORT_SCHEMA_VERSION",
    "Check",
    "Dimension",
    "ExportResult",
    "FabricationModel",
    "FabricationReport",
    "FabricationSettings",
    "FitContext",
    "OrientationCandidate",
    "PackingResult",
    "PartResult",
    "Provenance",
    "Status",
    "Target",
    "check_fit",
    "fabricate",
    "pack",
    "score_orientations",
    "thicken_to_solids",
    "to_dict",
    "validate",
]
