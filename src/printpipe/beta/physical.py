"""Physical print evidence packets for beta and dogfood runs."""

from __future__ import annotations

import os
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
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


def missing_required_evidence(
    evidence: PhysicalPrintEvidence,
    *,
    root: Path | None = None,
) -> list[str]:
    """Return missing fields needed before a physical print claim is credible.

    When ``root`` is provided, a photo artifact only counts if its file
    actually exists on disk (relative paths resolve against ``root``). The
    validation gate passes ``root`` so a hand-edited packet pointing at a
    nonexistent photo cannot be reported as passed evidence.
    """

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
    if printed_status and not _has_photo(evidence, root=root):
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
    missing_lines = _open_issue_lines(evidence=evidence, missing=missing)

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


def write_physical_evidence_files(
    *,
    run_root: str | os.PathLike[str],
    evidence: PhysicalPrintEvidence,
    directory_name: str = "90_physical",
    copy_artifacts: bool = False,
) -> dict[str, Any]:
    """Write physical evidence JSON and Markdown into a run folder."""

    root = Path(run_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    output_dir = root / directory_name
    output_dir.mkdir(parents=True, exist_ok=True)

    if copy_artifacts:
        evidence = replace(
            evidence,
            artifacts=_copy_artifacts_into_packet(
                root=root,
                output_dir=output_dir,
                artifacts=evidence.artifacts,
            ),
        )

    json_path = output_dir / "physical_evidence.json"
    markdown_path = output_dir / "physical_evidence.md"
    json_path.write_text(
        json.dumps(evidence.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_physical_evidence_markdown(evidence),
        encoding="utf-8",
    )
    return {
        "directory": str(output_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "missing_required_evidence": missing_required_evidence(evidence),
    }


def _copy_artifacts_into_packet(
    *,
    root: Path,
    output_dir: Path,
    artifacts: Sequence[PhysicalArtifact],
) -> tuple[PhysicalArtifact, ...]:
    copied: list[PhysicalArtifact] = []
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()

    for artifact in artifacts:
        source = Path(os.fspath(artifact.path)).expanduser()
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)

        destination = _unique_destination(
            artifact_dir,
            _safe_artifact_name(source.name),
            used_names,
        )
        if source != destination.resolve():
            shutil.copy2(source, destination)
        relative_path = destination.relative_to(root).as_posix()
        copied.append(replace(artifact, path=relative_path))

    return tuple(copied)


def _open_issue_lines(
    *,
    evidence: PhysicalPrintEvidence,
    missing: Sequence[str],
) -> str:
    lines: list[str] = []
    if evidence.print_status.lower() not in PRINTED_STATUSES:
        lines.append("- Physical print not recorded yet")
    lines.extend(f"- {item}" for item in missing)
    return "\n".join(lines) if lines else "- No missing required evidence"


def _safe_artifact_name(name: str) -> str:
    stem = Path(name).stem.lower()
    suffix = Path(name).suffix.lower()
    safe_stem = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in stem
    ).strip("-")
    while "--" in safe_stem:
        safe_stem = safe_stem.replace("--", "-")
    return f"{safe_stem or 'artifact'}{suffix}"


def _unique_destination(directory: Path, name: str, used_names: set[str]) -> Path:
    candidate = directory / name
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while candidate.name in used_names or candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    used_names.add(candidate.name)
    return candidate


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


def _has_photo(evidence: PhysicalPrintEvidence, *, root: Path | None = None) -> bool:
    for artifact in evidence.artifacts:
        kind = artifact.kind.lower()
        raw_path = os.fspath(artifact.path)
        looks_like_photo = kind == "photo" or raw_path.lower().endswith(
            (".jpg", ".jpeg", ".png", ".heic", ".webp")
        )
        if not looks_like_photo:
            continue
        if root is None:
            return True
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.is_file():
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
    "write_physical_evidence_files",
]
