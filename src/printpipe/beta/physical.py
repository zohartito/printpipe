"""Physical print evidence packets for beta and dogfood runs."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

PHYSICAL_EVIDENCE_SCHEMA_VERSION = 1

PHYSICAL_EVIDENCE_REQUIRED_HEADINGS = (
    "Run Context",
    "Print Setup",
    "Observed Results",
    "Artifacts",
    "Open Issues",
)

PRINTED_STATUSES = frozenset({"passed", "failed", "partial"})


@dataclass(frozen=True)
class PhysicalArtifact:
    """Artifact reference attached to physical print evidence."""

    label: str
    path: str | os.PathLike[str]
    kind: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize the artifact reference to JSON-friendly primitives."""

        return {
            "label": self.label,
            "path": os.fspath(self.path),
            "kind": self.kind,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PhysicalPrintEvidence:
    """Structured observations from a real printed coupon or object."""

    run_id: str
    material: str
    printer: str
    object_label: str
    print_type: str
    print_status: str
    operator: str = ""
    started_at: str = ""
    completed_at: str = ""
    slice_status: str = ""
    filament_drying: str = ""
    bed_prep: str = ""
    first_layer: str = ""
    adhesion: str = ""
    warping: str = ""
    stringing: str = ""
    layer_bonding: str = ""
    flex_recovery: str = ""
    support_removal: str = ""
    dimensions_mm: Mapping[str, float] | None = None
    artifacts: tuple[PhysicalArtifact, ...] = ()
    notes: tuple[str, ...] = ()
    schema_version: int = field(default=PHYSICAL_EVIDENCE_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize physical evidence to JSON-friendly primitives."""

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "material": self.material,
            "printer": self.printer,
            "object_label": self.object_label,
            "print_type": self.print_type,
            "print_status": self.print_status,
            "operator": self.operator,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "slice_status": self.slice_status,
            "filament_drying": self.filament_drying,
            "bed_prep": self.bed_prep,
            "first_layer": self.first_layer,
            "adhesion": self.adhesion,
            "warping": self.warping,
            "stringing": self.stringing,
            "layer_bonding": self.layer_bonding,
            "flex_recovery": self.flex_recovery,
            "support_removal": self.support_removal,
            "dimensions_mm": dict(self.dimensions_mm or {}),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "notes": list(self.notes),
        }


def build_physical_print_evidence(
    *,
    run_id: str,
    material: str,
    printer: str,
    object_label: str,
    print_type: str,
    print_status: str,
    operator: str = "",
    started_at: str = "",
    completed_at: str = "",
    slice_status: str = "",
    filament_drying: str = "",
    bed_prep: str = "",
    first_layer: str = "",
    adhesion: str = "",
    warping: str = "",
    stringing: str = "",
    layer_bonding: str = "",
    flex_recovery: str = "",
    support_removal: str = "",
    dimensions_mm: Mapping[str, float] | None = None,
    artifacts: Sequence[PhysicalArtifact | Mapping[str, object]] = (),
    notes: Sequence[str] = (),
) -> PhysicalPrintEvidence:
    """Build a normalized physical print evidence packet."""

    return PhysicalPrintEvidence(
        run_id=run_id,
        material=material,
        printer=printer,
        object_label=object_label,
        print_type=print_type,
        print_status=print_status,
        operator=operator,
        started_at=started_at,
        completed_at=completed_at,
        slice_status=slice_status,
        filament_drying=filament_drying,
        bed_prep=bed_prep,
        first_layer=first_layer,
        adhesion=adhesion,
        warping=warping,
        stringing=stringing,
        layer_bonding=layer_bonding,
        flex_recovery=flex_recovery,
        support_removal=support_removal,
        dimensions_mm=dimensions_mm,
        artifacts=tuple(_coerce_artifact(artifact) for artifact in artifacts),
        notes=tuple(str(note) for note in notes),
    )


def missing_required_evidence(evidence: PhysicalPrintEvidence) -> list[str]:
    """Return missing fields needed before a physical print claim is credible."""

    missing: list[str] = []

    for field_name in (
        "run_id",
        "material",
        "printer",
        "object_label",
        "print_type",
        "print_status",
        "operator",
    ):
        if not _has_text(getattr(evidence, field_name)):
            missing.append(field_name)

    printed_status = evidence.print_status.lower() in PRINTED_STATUSES
    if printed_status and not _has_photo(evidence):
        missing.append("photo artifact")

    if not printed_status:
        return missing

    material_family = _material_family(evidence.material)
    if material_family == "tpu":
        _require_text(
            evidence,
            missing,
            ("filament_drying", "layer_bonding", "flex_recovery"),
        )
    elif material_family == "petg":
        _require_text(
            evidence,
            missing,
            ("first_layer", "adhesion", "warping", "stringing"),
        )
    elif material_family == "pla":
        _require_text(evidence, missing, ("first_layer", "adhesion"))

    return missing


def render_physical_evidence_markdown(evidence: PhysicalPrintEvidence) -> str:
    """Render a physical print evidence packet as Markdown."""

    dimensions = _format_dimensions(evidence.dimensions_mm)
    artifacts = _artifact_lines(evidence.artifacts)
    notes = _list_lines(evidence.notes) or "- None recorded"
    missing = missing_required_evidence(evidence)
    missing_lines = _list_lines(missing) if missing else "- No missing required evidence"

    return f"""# PrintPipe Physical Print Evidence

## Run Context
- Run ID: {evidence.run_id}
- Object: {evidence.object_label}
- Print type: {evidence.print_type}
- Print status: {evidence.print_status}
- Operator: {evidence.operator or "unrecorded"}

## Print Setup
- Printer: {evidence.printer}
- Material: {evidence.material}
- Slice status: {evidence.slice_status or "unrecorded"}
- Filament drying: {evidence.filament_drying or "unrecorded"}
- Bed prep: {evidence.bed_prep or "unrecorded"}
- Started at: {evidence.started_at or "unrecorded"}
- Completed at: {evidence.completed_at or "unrecorded"}

## Observed Results
- First layer: {evidence.first_layer or "unrecorded"}
- Adhesion: {evidence.adhesion or "unrecorded"}
- Warping: {evidence.warping or "unrecorded"}
- Stringing: {evidence.stringing or "unrecorded"}
- Layer bonding: {evidence.layer_bonding or "unrecorded"}
- Flex recovery: {evidence.flex_recovery or "unrecorded"}
- Support removal: {evidence.support_removal or "unrecorded"}
- Dimensions: {dimensions}

## Artifacts
{artifacts}

## Open Issues
{missing_lines}

## Notes
{notes}
"""


def _coerce_artifact(
    artifact: PhysicalArtifact | Mapping[str, object],
) -> PhysicalArtifact:
    if isinstance(artifact, PhysicalArtifact):
        return artifact

    label = artifact.get("label")
    path = artifact.get("path")
    if label is None:
        raise ValueError("physical artifacts require a label")
    if path is None:
        raise ValueError("physical artifacts require a path")

    return PhysicalArtifact(
        label=str(label),
        path=os.fspath(path),
        kind=_optional_text(artifact.get("kind")),
        notes=_optional_text(artifact.get("notes")),
    )


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _has_text(value: object) -> bool:
    return bool(str(value).strip())


def _has_photo(evidence: PhysicalPrintEvidence) -> bool:
    for artifact in evidence.artifacts:
        kind = artifact.kind.lower()
        path = os.fspath(artifact.path).lower()
        if kind == "photo" or path.endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
            return True
    return False


def _material_family(material: str) -> str:
    normalized = material.lower()
    if "tpu" in normalized or "flex" in normalized:
        return "tpu"
    if "petg" in normalized:
        return "petg"
    if "pla" in normalized:
        return "pla"
    return "other"


def _require_text(
    evidence: PhysicalPrintEvidence,
    missing: list[str],
    field_names: Sequence[str],
) -> None:
    for field_name in field_names:
        if not _has_text(getattr(evidence, field_name)):
            missing.append(field_name)


def _format_dimensions(dimensions_mm: Mapping[str, float] | None) -> str:
    if not dimensions_mm:
        return "unrecorded"
    return ", ".join(
        f"{axis}={value:g} mm"
        for axis, value in sorted(dimensions_mm.items())
    )


def _artifact_lines(artifacts: Sequence[PhysicalArtifact]) -> str:
    if not artifacts:
        return "- None recorded"
    return "\n".join(
        f"- {artifact.label}: {os.fspath(artifact.path)}"
        + (f" ({artifact.notes})" if artifact.notes else "")
        for artifact in artifacts
    )


def _list_lines(values: Sequence[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


__all__ = [
    "PHYSICAL_EVIDENCE_REQUIRED_HEADINGS",
    "PHYSICAL_EVIDENCE_SCHEMA_VERSION",
    "PhysicalArtifact",
    "PhysicalPrintEvidence",
    "build_physical_print_evidence",
    "missing_required_evidence",
    "render_physical_evidence_markdown",
]
