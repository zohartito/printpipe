"""Beta failure report data model and Markdown parsing helpers."""

from __future__ import annotations

import os
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
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


def render_failure_report_markdown(report: FailureReport) -> str:
    """Render a beta failure report as Markdown."""

    symptoms = _list_lines(report.symptoms) or "- None recorded"
    artifacts = _artifact_lines(report.artifacts)

    return f"""# PrintPipe Beta Failure Report

## Run Context
- Run ID: {report.run_id}
- Input type: {report.input_type}
- Material: {report.material}
- Printer: {report.printer}

## Failure Details
- Failed stage: {report.failed_stage}

## Symptoms
{symptoms}

## Artifacts
{artifacts}

## Reproduction
```bash
{report.reproduction_command}
```

## Physical Print Status
- {report.physical_print_status}

## Triage Notes
- Add triage owner, root cause, and rule updates after review.
"""


def write_failure_report_files(
    *,
    run_root: str | os.PathLike[str],
    report: FailureReport,
    directory_name: str = "90_beta",
    copy_artifacts: bool = False,
) -> dict[str, Any]:
    """Write beta failure JSON and Markdown into a run folder."""

    root = Path(run_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    output_dir = root / directory_name
    output_dir.mkdir(parents=True, exist_ok=True)

    if copy_artifacts:
        report = replace(
            report,
            artifacts=_copy_artifacts_into_packet(
                root=root,
                output_dir=output_dir,
                artifacts=report.artifacts,
            ),
        )

    json_path = output_dir / "failure_report.json"
    markdown_path = output_dir / "failure_report.md"
    markdown = render_failure_report_markdown(report)
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return {
        "directory": str(output_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "missing_required_headings": missing_required_headings(markdown),
    }


def _copy_artifacts_into_packet(
    *,
    root: Path,
    output_dir: Path,
    artifacts: Sequence[FailureArtifact],
) -> tuple[FailureArtifact, ...]:
    copied: list[FailureArtifact] = []
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


def _artifact_lines(artifacts: Sequence[FailureArtifact]) -> str:
    if not artifacts:
        return "- None recorded"
    return "\n".join(
        f"- {artifact.label}: {os.fspath(artifact.path)}"
        + (f" ({artifact.notes})" if artifact.notes else "")
        for artifact in artifacts
    )


def _list_lines(values: Sequence[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


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
    "render_failure_report_markdown",
    "write_failure_report_files",
]
