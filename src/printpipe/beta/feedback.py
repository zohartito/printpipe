"""Trusted-user beta feedback packet helpers."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

TRUSTED_FEEDBACK_SCHEMA_VERSION = 1
DEFAULT_REQUIRED_TRUSTED_USERS = 3

TRUSTED_FEEDBACK_REQUIRED_HEADINGS = (
    "Run Context",
    "Tester",
    "Outcome",
    "Issues",
    "Artifacts",
    "Recommendation",
)

OUTCOMES = ("passed", "failed", "partial", "not_run")
TESTER_TYPES = ("trusted_user", "internal", "coordinator")
WOULD_PRINT_VALUES = ("yes", "no", "unknown")
TRUSTED_FEEDBACK_PLAN_PROOF_BOUNDARY = (
    "A generated feedback plan is not trusted-user evidence. Only recorded "
    "trusted-user feedback packets count toward the beta gate."
)


@dataclass(frozen=True)
class FeedbackArtifact:
    """Artifact reference attached to trusted-user feedback."""

    label: str
    path: str | os.PathLike[str]
    kind: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "label": self.label,
            "path": os.fspath(self.path),
            "kind": self.kind,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class TrustedUserFeedback:
    """Structured feedback from a beta tester."""

    run_id: str
    tester: str
    tester_type: str
    input_type: str
    material: str
    printer: str
    outcome: str
    summary: str
    issues: tuple[str, ...]
    would_print: str
    recommendation: str
    artifacts: tuple[FeedbackArtifact, ...]
    schema_version: int = field(default=TRUSTED_FEEDBACK_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "tester": self.tester,
            "tester_type": self.tester_type,
            "input_type": self.input_type,
            "material": self.material,
            "printer": self.printer,
            "outcome": self.outcome,
            "summary": self.summary,
            "issues": list(self.issues),
            "would_print": self.would_print,
            "recommendation": self.recommendation,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


def build_trusted_user_feedback(
    *,
    run_id: str,
    tester: str,
    tester_type: str,
    input_type: str,
    material: str,
    printer: str,
    outcome: str,
    summary: str,
    issues: Sequence[str],
    would_print: str,
    recommendation: str,
    artifacts: Sequence[FeedbackArtifact | Mapping[str, object]],
) -> TrustedUserFeedback:
    """Build a normalized trusted-user feedback packet."""

    normalized_tester = tester.strip()
    if not normalized_tester:
        raise ValueError("trusted-user feedback requires a tester")
    normalized_summary = summary.strip()
    if not normalized_summary:
        raise ValueError("trusted-user feedback requires a summary")
    return TrustedUserFeedback(
        run_id=run_id,
        tester=normalized_tester,
        tester_type=_choice(tester_type, TESTER_TYPES, "tester_type"),
        input_type=input_type,
        material=material,
        printer=printer,
        outcome=_choice(outcome, OUTCOMES, "outcome"),
        summary=normalized_summary,
        issues=tuple(str(issue) for issue in issues),
        would_print=_choice(would_print, WOULD_PRINT_VALUES, "would_print"),
        recommendation=recommendation,
        artifacts=tuple(_coerce_artifact(artifact) for artifact in artifacts),
    )


def parse_trusted_feedback_sections(markdown: str) -> dict[str, str]:
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


def missing_required_feedback_headings(markdown: str) -> list[str]:
    """Return required trusted-feedback headings absent from Markdown."""

    sections = parse_trusted_feedback_sections(markdown)
    return [
        heading
        for heading in TRUSTED_FEEDBACK_REQUIRED_HEADINGS
        if heading not in sections
    ]


def render_trusted_user_feedback_markdown(feedback: TrustedUserFeedback) -> str:
    """Render trusted-user feedback as Markdown."""

    issues = _list_lines(feedback.issues) or "- None recorded"
    artifacts = _artifact_lines(feedback.artifacts)
    return f"""# PrintPipe Trusted-User Feedback

## Run Context
- Run ID: {feedback.run_id}
- Input type: {feedback.input_type}
- Material: {feedback.material}
- Printer: {feedback.printer}

## Tester
- Name: {feedback.tester}
- Type: {feedback.tester_type}

## Outcome
- Outcome: {feedback.outcome}
- Summary: {feedback.summary}
- Would print: {feedback.would_print}

## Issues
{issues}

## Artifacts
{artifacts}

## Recommendation
- {feedback.recommendation}
"""


def write_trusted_user_feedback_files(
    *,
    run_root: str | os.PathLike[str],
    feedback: TrustedUserFeedback,
    directory_name: str = "90_beta",
    copy_artifacts: bool = False,
) -> dict[str, Any]:
    """Write trusted-user feedback JSON and Markdown into a run folder."""

    root = Path(run_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    output_dir = root / directory_name
    output_dir.mkdir(parents=True, exist_ok=True)
    if copy_artifacts:
        feedback = replace(
            feedback,
            artifacts=_copy_artifacts_into_packet(
                root=root,
                output_dir=output_dir,
                artifacts=feedback.artifacts,
            ),
        )

    json_path = output_dir / "trusted_user_feedback.json"
    markdown_path = output_dir / "trusted_user_feedback.md"
    markdown = render_trusted_user_feedback_markdown(feedback)
    json_path.write_text(
        json.dumps(feedback.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return {
        "directory": str(output_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "missing_required_headings": missing_required_feedback_headings(markdown),
    }


def build_trusted_user_feedback_status(
    runs_dir: str | Path,
    *,
    required_trusted_user_count: int = DEFAULT_REQUIRED_TRUSTED_USERS,
) -> dict[str, Any]:
    """Summarize trusted-user beta feedback across run folders."""

    root = Path(runs_dir).expanduser().resolve()
    packets = _load_feedback_packets(root)
    trusted_packets = [
        packet for packet in packets if packet["tester_type"] == "trusted_user"
    ]
    completed_trusted_packets = [
        packet for packet in trusted_packets if packet["outcome"] != "not_run"
    ]
    trusted_users = sorted({packet["tester"] for packet in completed_trusted_packets})
    not_run_trusted_users = sorted(
        {
            packet["tester"]
            for packet in trusted_packets
            if packet["outcome"] == "not_run"
        }
    )
    missing_count = max(required_trusted_user_count - len(trusted_users), 0)
    outcome_counts = {
        outcome: sum(1 for packet in packets if packet["outcome"] == outcome)
        for outcome in OUTCOMES
    }
    return {
        "schema_version": TRUSTED_FEEDBACK_SCHEMA_VERSION,
        "runs_dir": str(root),
        "overall_status": "passed" if missing_count == 0 else "insufficient_feedback",
        "required_trusted_user_count": required_trusted_user_count,
        "unique_trusted_user_count": len(trusted_users),
        "completed_trusted_user_count": len(trusted_users),
        "missing_trusted_user_count": missing_count,
        "trusted_users": trusted_users,
        "not_run_trusted_users": not_run_trusted_users,
        "packet_count": len(packets),
        "trusted_user_packet_count": len(trusted_packets),
        "completed_trusted_user_packet_count": len(completed_trusted_packets),
        "outcome_counts": outcome_counts,
        "packets": packets,
    }


def render_trusted_user_feedback_status(status: Mapping[str, Any]) -> str:
    """Render a human-readable trusted-user beta feedback status."""

    current = int(status.get("unique_trusted_user_count") or 0)
    required = int(status.get("required_trusted_user_count") or 0)
    lines = [
        "PrintPipe Trusted-User Feedback",
        f"runs dir: {status.get('runs_dir', 'unknown')}",
        f"overall: {status.get('overall_status', 'unknown')}",
        f"trusted users: {current} / {required}",
        f"feedback packets: {status.get('packet_count', 0)}",
        "",
    ]
    users = status.get("trusted_users")
    if isinstance(users, list) and users:
        lines.append("Trusted users:")
        lines.extend(f"- {user}" for user in users)
        lines.append("")
    return "\n".join(lines)


def build_trusted_user_feedback_plan(
    runs_dir: str | Path,
    *,
    required_trusted_user_count: int = DEFAULT_REQUIRED_TRUSTED_USERS,
) -> dict[str, Any]:
    """Turn missing trusted-user feedback into exact next actions."""

    status = build_trusted_user_feedback_status(
        runs_dir,
        required_trusted_user_count=required_trusted_user_count,
    )
    current = int(status.get("unique_trusted_user_count") or 0)
    required = int(status.get("required_trusted_user_count") or required_trusted_user_count)
    missing = max(required - current, 0)
    actions = [
        _trusted_feedback_action(slot=slot)
        for slot in range(current + 1, required + 1)
    ]
    return {
        "schema_version": TRUSTED_FEEDBACK_SCHEMA_VERSION,
        "runs_dir": str(Path(runs_dir).expanduser().resolve()),
        "overall_status": "ready" if not actions else "action_required",
        "required_trusted_user_count": required,
        "trusted_user_count": current,
        "missing_trusted_user_count": missing,
        "trusted_users": status.get("trusted_users", []),
        "packet_count": status.get("packet_count", 0),
        "proof_boundary": TRUSTED_FEEDBACK_PLAN_PROOF_BOUNDARY,
        "action_count": len(actions),
        "actions": actions,
    }


def render_trusted_user_feedback_plan(plan: Mapping[str, Any]) -> str:
    """Render a trusted-user feedback action plan."""

    current = int(plan.get("trusted_user_count") or 0)
    required = int(plan.get("required_trusted_user_count") or 0)
    lines = [
        "PrintPipe Trusted-User Feedback Plan",
        f"runs dir: {plan.get('runs_dir', 'unknown')}",
        f"overall: {plan.get('overall_status', 'unknown')}",
        f"trusted users: {current} / {required}",
        f"action required: {plan.get('action_count', 0)}",
        "",
        str(plan.get("proof_boundary", TRUSTED_FEEDBACK_PLAN_PROOF_BOUNDARY)),
        "",
    ]
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        lines.append("No trusted-user feedback actions required.")
        lines.append("")
        return "\n".join(lines)
    lines.append("Actions:")
    for action in actions:
        item = action if isinstance(action, dict) else {}
        lines.append(
            f"- tester slot {item.get('slot', '?')}: {item.get('status', 'unknown')}"
        )
        detail = str(item.get("detail") or "")
        if detail:
            lines.append(f"  detail: {detail}")
        command = str(item.get("record_command") or "")
        if command:
            lines.append(f"  record: {command}")
    lines.append("")
    return "\n".join(lines)


def _trusted_feedback_action(*, slot: int) -> dict[str, Any]:
    return {
        "slot": slot,
        "label": f"Trusted tester {slot}",
        "status": "action_required",
        "detail": (
            "Give a trusted user a PrintPipe run to review, collect their outcome, "
            "and attach relevant screenshots, logs, or photos."
        ),
        "record_command": (
            'printpipe record-beta-feedback "runs/<run-id>" '
            f'--tester "<trusted-user-{slot}>" '
            '--input-type existing_stl --material "<material>" '
            '--printer "Bambu Lab P2S" --outcome passed '
            '--summary "<what happened>" --would-print no '
            '--recommendation needs_review '
            '--artifact "Run report|report|runs/<run-id>/80_reports/run_report.html|reviewed by tester"'
        ),
        "required_fields": [
            "tester",
            "run_root",
            "input_type",
            "material",
            "printer",
            "outcome",
            "summary",
            "would_print",
            "recommendation",
        ],
    }


def _load_feedback_packets(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    packets: list[dict[str, Any]] = []
    for feedback_path in sorted(runs_dir.glob("*/90_beta/trusted_user_feedback.json")):
        try:
            payload = json.loads(feedback_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        packets.append(_packet_summary(payload, feedback_path=feedback_path))
    return packets


def _packet_summary(
    payload: Mapping[str, Any],
    *,
    feedback_path: Path,
) -> dict[str, Any]:
    run_root = feedback_path.parents[1]
    markdown_path = feedback_path.with_suffix(".md")
    return {
        "run_id": str(payload.get("run_id") or run_root.name),
        "run_root": str(run_root),
        "json_path": str(feedback_path),
        "markdown_path": str(markdown_path) if markdown_path.exists() else "",
        "tester": str(payload.get("tester") or ""),
        "tester_type": str(payload.get("tester_type") or ""),
        "input_type": str(payload.get("input_type") or ""),
        "material": str(payload.get("material") or ""),
        "printer": str(payload.get("printer") or ""),
        "outcome": str(payload.get("outcome") or ""),
        "would_print": str(payload.get("would_print") or ""),
        "recommendation": str(payload.get("recommendation") or ""),
        "issue_count": len(_list(payload.get("issues"))),
        "artifact_count": len(_list(payload.get("artifacts"))),
    }


def _copy_artifacts_into_packet(
    *,
    root: Path,
    output_dir: Path,
    artifacts: Sequence[FeedbackArtifact],
) -> tuple[FeedbackArtifact, ...]:
    copied: list[FeedbackArtifact] = []
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
        copied.append(replace(artifact, path=destination.relative_to(root).as_posix()))
    return tuple(copied)


def _coerce_artifact(
    artifact: FeedbackArtifact | Mapping[str, object],
) -> FeedbackArtifact:
    if isinstance(artifact, FeedbackArtifact):
        return artifact
    label = artifact.get("label")
    path = artifact.get("path")
    if label is None:
        raise ValueError("feedback artifacts require a label")
    if path is None:
        raise ValueError("feedback artifacts require a path")
    return FeedbackArtifact(
        label=str(label),
        path=os.fspath(path),
        kind=_optional_text(artifact.get("kind")),
        notes=_optional_text(artifact.get("notes")),
    )


def _choice(value: str, choices: Sequence[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in choices:
        expected = ", ".join(choices)
        raise ValueError(f"{field_name} must be one of: {expected}")
    return normalized


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


def _artifact_lines(artifacts: Sequence[FeedbackArtifact]) -> str:
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


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "DEFAULT_REQUIRED_TRUSTED_USERS",
    "OUTCOMES",
    "TESTER_TYPES",
    "TRUSTED_FEEDBACK_REQUIRED_HEADINGS",
    "TRUSTED_FEEDBACK_SCHEMA_VERSION",
    "TRUSTED_FEEDBACK_PLAN_PROOF_BOUNDARY",
    "FeedbackArtifact",
    "TrustedUserFeedback",
    "build_trusted_user_feedback",
    "build_trusted_user_feedback_plan",
    "build_trusted_user_feedback_status",
    "missing_required_feedback_headings",
    "parse_trusted_feedback_sections",
    "render_trusted_user_feedback_plan",
    "render_trusted_user_feedback_markdown",
    "render_trusted_user_feedback_status",
    "write_trusted_user_feedback_files",
]
