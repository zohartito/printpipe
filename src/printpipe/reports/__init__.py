"""Receipt serialization and report rendering for PrintPipe runs."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt
from printpipe.runs.paths import RunLayout


def artifact_to_dict(artifact: Artifact, *, run_root: Path | None = None) -> dict[str, Any]:
    """Serialize an artifact contract to a JSON-friendly dictionary."""

    return {
        "kind": artifact.kind.value,
        "path": _json_friendly(artifact.path, run_root=run_root),
        "label": artifact.label,
        "metadata": _json_friendly(artifact.metadata, run_root=run_root),
    }


def stage_receipt_to_dict(receipt: StageReceipt, *, run_root: Path | None = None) -> dict[str, Any]:
    """Serialize a stage receipt contract to a JSON-friendly dictionary."""

    return {
        "stage": receipt.stage,
        "status": receipt.status.value,
        "message": receipt.message,
        "artifacts": [
            artifact_to_dict(artifact, run_root=run_root)
            for artifact in receipt.artifacts
        ],
        "metrics": _json_friendly(receipt.metrics, run_root=run_root),
    }


def build_run_report_dict(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    warnings: Sequence[str] = (),
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    pre_print_checklist: Sequence[Mapping[str, Any] | str] = (),
    physical_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the structured run report payload."""

    stage_dicts = [stage_receipt_to_dict(stage, run_root=layout.root) for stage in stages]
    artifacts = [
        artifact
        for stage in stage_dicts
        for artifact in stage["artifacts"]
    ]

    report = {
        "schema_version": 1,
        "run_id": layout.run_id,
        "stages": stage_dicts,
        "artifacts": artifacts,
        "warnings": list(warnings),
        "settings_changes": _json_friendly(settings_changes, run_root=layout.root),
        "pre_print_checklist": _json_friendly(pre_print_checklist, run_root=layout.root),
    }
    if physical_evidence is not None:
        report["physical_evidence"] = _json_friendly(
            physical_evidence,
            run_root=layout.root,
        )
    return report


def render_markdown_report(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    warnings: Sequence[str] = (),
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    pre_print_checklist: Sequence[Mapping[str, Any] | str] = (),
    physical_evidence: Mapping[str, Any] | None = None,
) -> str:
    """Render a local Markdown run report."""

    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
        physical_evidence=physical_evidence,
    )
    return render_markdown_report_dict(layout, report_dict)


def render_markdown_report_dict(
    layout: RunLayout,
    report_dict: Mapping[str, Any],
) -> str:
    """Render a local Markdown run report from a structured report dictionary."""

    stages = _as_list(report_dict.get("stages"))
    artifacts = _as_list(report_dict.get("artifacts"))
    warnings = _as_list(report_dict.get("warnings"))
    settings_changes = _as_list(report_dict.get("settings_changes"))
    pre_print_checklist = _as_list(report_dict.get("pre_print_checklist"))
    physical_evidence = _mapping(report_dict.get("physical_evidence"))

    lines = [
        f"# PrintPipe Run Report: {report_dict.get('run_id', layout.run_id)}",
        "",
        "## Stages",
    ]

    if stages:
        for stage in stages:
            lines.extend(_render_stage_mapping(layout, stage))
    else:
        lines.append("")
        lines.append("No stages recorded yet.")

    prompt_reference_lines = _render_prompt_reference_section_from_mappings(stages)
    if prompt_reference_lines:
        lines.extend(["", *prompt_reference_lines])

    lines.extend(["", "## Artifacts"])
    if artifacts:
        for artifact in artifacts:
            lines.append(_render_artifact_mapping(layout, artifact))
    else:
        lines.append("No artifacts recorded yet.")

    physical_lines = _render_physical_evidence_section(layout, physical_evidence)
    if physical_lines:
        lines.extend(["", *physical_lines])

    lines.extend(["", "## Warnings"])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("No warnings recorded yet.")

    lines.extend(["", "## Settings Changes"])
    if settings_changes:
        for change in settings_changes:
            lines.append(f"- {_format_report_value(change, run_root=layout.root)}")
    else:
        lines.append("No settings changes recorded yet.")

    lines.extend(["", "## Pre-print Checklist"])
    if pre_print_checklist:
        for item in pre_print_checklist:
            lines.append(f"- {_format_report_value(item, run_root=layout.root)}")
    else:
        lines.append("No pre-print checklist recorded for this report.")

    return "\n".join(lines) + "\n"


def write_run_report(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    warnings: Sequence[str] = (),
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    pre_print_checklist: Sequence[Mapping[str, Any] | str] = (),
    physical_evidence: Mapping[str, Any] | None = None,
) -> tuple[Artifact, Artifact]:
    """Write JSON and Markdown run reports into the run layout reports directory."""

    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
        physical_evidence=physical_evidence,
    )
    return write_run_report_dict(layout, report_dict)


def write_run_report_dict(
    layout: RunLayout,
    report_dict: Mapping[str, Any],
) -> tuple[Artifact, Artifact]:
    """Write JSON and Markdown reports from a structured report dictionary."""

    layout.reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = layout.reports_dir / "run_report.json"
    markdown_path = layout.reports_dir / "run_report.md"

    json_path.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown_report_dict(layout, report_dict)
    markdown_path.write_text(markdown, encoding="utf-8")

    return (
        Artifact(kind=ArtifactKind.REPORT, path=json_path, label="Run report JSON"),
        Artifact(kind=ArtifactKind.REPORT, path=markdown_path, label="Run report Markdown"),
    )


def _render_stage_mapping(layout: RunLayout, stage: Any) -> list[str]:
    if not isinstance(stage, Mapping):
        return ["", f"### {_format_report_value(stage, run_root=layout.root)}", ""]
    lines = [
        "",
        f"### {stage.get('stage', 'unknown')} - {stage.get('status', 'unknown')}",
        "",
        str(stage.get("message", "")),
    ]
    artifacts = _as_list(stage.get("artifacts"))
    if artifacts:
        lines.append("")
        lines.append("Artifacts:")
        for artifact in artifacts:
            lines.append(_render_artifact_mapping(layout, artifact))
    metrics = stage.get("metrics")
    if metrics:
        lines.append("")
        lines.append(f"Metrics: {_format_report_value(metrics, run_root=layout.root)}")
    return lines


def _render_artifact_mapping(layout: RunLayout, artifact: Any) -> str:
    if not isinstance(artifact, Mapping):
        return f"- {_format_report_value(artifact, run_root=layout.root)}"
    label = str(artifact.get("label") or "Artifact")
    kind = str(artifact.get("kind") or "artifact")
    path = artifact.get("path")
    if not path:
        return f"- {label} ({kind})"
    display_path = str(path)
    link_path = _path_string_to_link(display_path, layout=layout)
    return f"- {label} ({kind}): [{display_path}]({link_path})"


def _render_prompt_reference_section_from_mappings(stages: Sequence[Any]) -> list[str]:
    receipt = _prompt_reference_mapping(stages)
    if receipt is None:
        return []
    metrics = _mapping(receipt.get("metrics"))
    quote = _mapping(metrics.get("provider_quote"))
    provider = str(quote.get("provider") or metrics.get("provider") or "unknown")
    message = str(receipt.get("message", ""))
    lines = [
        "## Prompt Reference",
        f"- Provider: {provider}",
        f"- Status: {receipt.get('status', 'unknown')}",
        f"- Message: {message}",
        f"- Privacy: {quote.get('privacy_mode', 'not recorded')}",
        f"- Estimated cost: {_format_money(quote.get('estimated_cost_usd'))}",
        f"- Max cost: {_format_money(quote.get('max_cost_usd'))}",
        f"- Estimated latency: {_format_seconds(quote.get('estimated_seconds'))}",
        f"- Budget: {_prompt_budget_status_from_mapping(receipt)}",
        f"- Remote upload: {_format_bool(quote.get('remote_upload'))}",
        f"- Provider prompt storage: {_format_bool(quote.get('stores_prompt_with_provider'))}",
    ]
    return lines


def _render_physical_evidence_section(
    layout: RunLayout,
    physical_evidence: Mapping[str, Any],
) -> list[str]:
    if not physical_evidence:
        return []
    lines = [
        "## Physical Evidence",
        f"- Print status: {physical_evidence.get('print_status', 'not recorded')}",
        f"- Object: {physical_evidence.get('object_label', 'not recorded')}",
        f"- Operator: {physical_evidence.get('operator', 'not recorded')}",
        f"- Material: {physical_evidence.get('material', 'not recorded')}",
        f"- Printer: {physical_evidence.get('printer', 'not recorded')}",
    ]
    packet_paths = _mapping(physical_evidence.get("packet_paths"))
    for label, path in (
        ("Evidence JSON", packet_paths.get("json")),
        ("Evidence Markdown", packet_paths.get("markdown")),
    ):
        if path:
            path_text = str(path)
            lines.append(
                f"- {label}: [{path_text}]({_path_string_to_link(path_text, layout=layout)})"
            )
    artifacts = _as_list(physical_evidence.get("artifacts"))
    if artifacts:
        lines.append("")
        lines.append("Physical artifacts:")
        for artifact in artifacts:
            lines.append(_render_artifact_mapping(layout, artifact))
    missing = [str(item) for item in _as_list(physical_evidence.get("missing_required_evidence"))]
    if missing:
        lines.append("")
        lines.append("Missing required evidence: " + ", ".join(missing))
    else:
        lines.append("")
        lines.append("No missing required evidence")
    return lines


def _prompt_reference_mapping(stages: Sequence[Any]) -> Mapping[str, Any] | None:
    for receipt in stages:
        if isinstance(receipt, Mapping) and receipt.get("stage") == "prompt_reference_generation":
            return receipt
    return None


def _prompt_budget_status_from_mapping(receipt: Mapping[str, Any]) -> str:
    message = str(receipt.get("message", "")).lower()
    metrics = _mapping(receipt.get("metrics"))
    quote = _mapping(metrics.get("provider_quote"))
    estimated_cost = quote.get("estimated_cost_usd")
    max_cost = quote.get("max_cost_usd")
    if "cost cap" in message or "exceeds cap" in message:
        return "blocked"
    if max_cost is None:
        return "not_capped"
    if estimated_cost is None:
        return "unchecked"
    try:
        estimate = float(estimated_cost)
        cap = float(max_cost)
    except (TypeError, ValueError):
        return "review"
    if estimate > cap:
        return "blocked"
    if str(receipt.get("status", "")) == "succeeded":
        return "within_cap"
    return "within_cap_pending"


def _format_money(value: Any) -> str:
    if value in {None, ""}:
        return "not estimated"
    try:
        return f"${float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _format_seconds(value: Any) -> str:
    if value in {None, ""}:
        return "not estimated"
    try:
        return f"{float(value):g} s"
    except (TypeError, ValueError):
        return str(value)


def _format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value in {None, ""}:
        return "not recorded"
    return str(value)


def _json_friendly(value: Any, *, run_root: Path | None = None) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return _path_to_string(value, root=run_root)
    if isinstance(value, Mapping):
        return {
            str(_json_friendly(key, run_root=run_root)): _json_friendly(nested, run_root=run_root)
            for key, nested in value.items()
        }
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [_json_friendly(item, run_root=run_root) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field: _json_friendly(getattr(value, field), run_root=run_root)
            for field in value.__dataclass_fields__
        }
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _format_report_value(value: Any, *, run_root: Path | None = None) -> str:
    friendly = _json_friendly(value, run_root=run_root)
    if isinstance(friendly, str):
        return friendly
    return json.dumps(friendly, sort_keys=True)


def _path_to_string(path: Path, *, root: Path | None = None) -> str:
    if root is None:
        return str(path)

    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return str(resolved_path)


def _path_to_link(path: Path, *, base_dir: Path) -> str:
    resolved_path = path.expanduser().resolve()
    resolved_base = base_dir.expanduser().resolve()
    return Path(os.path.relpath(resolved_path, start=resolved_base)).as_posix()


def _path_string_to_link(path: str, *, layout: RunLayout) -> str:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = layout.root / candidate
    return _path_to_link(candidate, base_dir=layout.reports_dir)


__all__ = [
    "artifact_to_dict",
    "build_run_report_dict",
    "render_markdown_report",
    "render_markdown_report_dict",
    "stage_receipt_to_dict",
    "write_run_report",
    "write_run_report_dict",
]
