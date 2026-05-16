"""Beta failure report data model and Markdown parsing helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

FAILURE_REPORT_SCHEMA_VERSION = 1

FAILURE_REPORT_REQUIRED_HEADINGS = (
    "Run Context",
    "Failure Details",
    "Symptoms",
    "Artifacts",
    "Reproduction",
    "Physical Print Status",
    "Triage Notes",
)


@dataclass(frozen=True)
class FailureArtifact:
    """Artifact reference attached to a beta failure report."""

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
class FailureReport:
    """Structured context for a failed beta run."""

    run_id: str
    input_type: str
    material: str
    printer: str
    failed_stage: str
    symptoms: tuple[str, ...]
    artifacts: tuple[FailureArtifact, ...]
    reproduction_command: str
    physical_print_status: str
    schema_version: int = field(default=FAILURE_REPORT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize failed-run context to a JSON-friendly dictionary."""

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "input_type": self.input_type,
            "material": self.material,
            "printer": self.printer,
            "failed_stage": self.failed_stage,
            "symptoms": list(self.symptoms),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "reproduction_command": self.reproduction_command,
            "physical_print_status": self.physical_print_status,
        }


def build_failure_report(
    *,
    run_id: str,
    input_type: str,
    material: str,
    printer: str,
    failed_stage: str,
    symptoms: Sequence[str],
    artifacts: Sequence[FailureArtifact | Mapping[str, object]],
    reproduction_command: str,
    physical_print_status: str,
) -> FailureReport:
    """Build a normalized beta failure report."""

    return FailureReport(
        run_id=run_id,
        input_type=input_type,
        material=material,
        printer=printer,
        failed_stage=failed_stage,
        symptoms=tuple(str(symptom) for symptom in symptoms),
        artifacts=tuple(_coerce_artifact(artifact) for artifact in artifacts),
        reproduction_command=reproduction_command,
        physical_print_status=physical_print_status,
    )


def parse_failure_report_sections(markdown: str) -> dict[str, str]:
    """Parse second-level Markdown headings into section bodies."""

    sections: dict[str, list[str]] = {}
    current_heading: str | None = None

    for line in markdown.splitlines():
        heading = _second_level_heading(line)
        if heading is not None:
            current_heading = heading
            sections.setdefault(current_heading, [])
            continue

        if current_heading is not None:
            sections[current_heading].append(line)

    return {
        heading: "\n".join(lines).strip("\n")
        for heading, lines in sections.items()
    }


def missing_required_headings(markdown: str) -> list[str]:
    """Return required failure-report headings that are absent from Markdown."""

    sections = parse_failure_report_sections(markdown)
    return [
        heading
        for heading in FAILURE_REPORT_REQUIRED_HEADINGS
        if heading not in sections
    ]


def _coerce_artifact(artifact: FailureArtifact | Mapping[str, object]) -> FailureArtifact:
    if isinstance(artifact, FailureArtifact):
        return artifact

    label = artifact.get("label")
    path = artifact.get("path")
    if label is None:
        raise ValueError("failure artifacts require a label")
    if path is None:
        raise ValueError("failure artifacts require a path")

    return FailureArtifact(
        label=str(label),
        path=os.fspath(path),
        kind=_optional_text(artifact.get("kind")),
        notes=_optional_text(artifact.get("notes")),
    )


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _second_level_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("## ") or stripped.startswith("### "):
        return None
    return stripped[3:].strip().rstrip("#").strip()


__all__ = [
    "FAILURE_REPORT_REQUIRED_HEADINGS",
    "FAILURE_REPORT_SCHEMA_VERSION",
    "FailureArtifact",
    "FailureReport",
    "build_failure_report",
    "missing_required_headings",
    "parse_failure_report_sections",
]
