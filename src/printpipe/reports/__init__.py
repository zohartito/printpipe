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
) -> dict[str, Any]:
    """Build the structured run report payload."""

    stage_dicts = [stage_receipt_to_dict(stage, run_root=layout.root) for stage in stages]
    artifacts = [
        artifact
        for stage in stage_dicts
        for artifact in stage["artifacts"]
    ]

    return {
        "schema_version": 1,
        "run_id": layout.run_id,
        "stages": stage_dicts,
        "artifacts": artifacts,
        "warnings": list(warnings),
        "settings_changes": _json_friendly(settings_changes, run_root=layout.root),
        "pre_print_checklist": _json_friendly(pre_print_checklist, run_root=layout.root),
    }


def render_markdown_report(
    layout: RunLayout,
    *,
    stages: Sequence[StageReceipt],
    warnings: Sequence[str] = (),
    settings_changes: Sequence[Mapping[str, Any] | str] = (),
    pre_print_checklist: Sequence[Mapping[str, Any] | str] = (),
) -> str:
    """Render a local Markdown run report."""

    lines = [
        f"# PrintPipe Run Report: {layout.run_id}",
        "",
        "## Stages",
    ]

    if stages:
        for receipt in stages:
            lines.extend(_render_stage(layout, receipt))
    else:
        lines.append("")
        lines.append("No stages recorded yet.")

    prompt_reference_lines = _render_prompt_reference_section(stages)
    if prompt_reference_lines:
        lines.extend(["", *prompt_reference_lines])

    lines.extend(["", "## Artifacts"])
    artifacts = [artifact for receipt in stages for artifact in receipt.artifacts]
    if artifacts:
        for artifact in artifacts:
            lines.append(_render_artifact(layout, artifact))
    else:
        lines.append("No artifacts recorded yet.")

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
) -> tuple[Artifact, Artifact]:
    """Write JSON and Markdown run reports into the run layout reports directory."""

    layout.reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = layout.reports_dir / "run_report.json"
    markdown_path = layout.reports_dir / "run_report.md"

    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    json_path.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")

    markdown = render_markdown_report(
        layout,
        stages=stages,
        warnings=warnings,
        settings_changes=settings_changes,
        pre_print_checklist=pre_print_checklist,
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    return (
        Artifact(kind=ArtifactKind.REPORT, path=json_path, label="Run report JSON"),
        Artifact(kind=ArtifactKind.REPORT, path=markdown_path, label="Run report Markdown"),
    )


def _render_stage(layout: RunLayout, receipt: StageReceipt) -> list[str]:
    lines = [
        "",
        f"### {receipt.stage} - {receipt.status.value}",
        "",
        receipt.message,
    ]
    if receipt.artifacts:
        lines.append("")
        lines.append("Artifacts:")
        for artifact in receipt.artifacts:
            lines.append(_render_artifact(layout, artifact))
    if receipt.metrics:
        lines.append("")
        lines.append(f"Metrics: {_format_report_value(receipt.metrics, run_root=layout.root)}")
    return lines


def _render_artifact(layout: RunLayout, artifact: Artifact) -> str:
    display_path = _path_to_string(artifact.path, root=layout.root)
    link_path = _path_to_link(artifact.path, base_dir=layout.reports_dir)
    return f"- {artifact.label} ({artifact.kind.value}): [{display_path}]({link_path})"


def _render_prompt_reference_section(stages: Sequence[StageReceipt]) -> list[str]:
    receipt = _prompt_reference_receipt(stages)
    if receipt is None:
        return []
    quote = _prompt_provider_quote(receipt.metrics)
    provider = str(quote.get("provider") or receipt.metrics.get("provider") or "unknown")
    lines = [
        "## Prompt Reference",
        f"- Provider: {provider}",
        f"- Status: {receipt.status.value}",
        f"- Message: {receipt.message}",
        f"- Privacy: {quote.get('privacy_mode', 'not recorded')}",
        f"- Estimated cost: {_format_money(quote.get('estimated_cost_usd'))}",
        f"- Max cost: {_format_money(quote.get('max_cost_usd'))}",
        f"- Estimated latency: {_format_seconds(quote.get('estimated_seconds'))}",
        f"- Budget: {_prompt_budget_status(receipt)}",
        f"- Remote upload: {_format_bool(quote.get('remote_upload'))}",
        f"- Provider prompt storage: {_format_bool(quote.get('stores_prompt_with_provider'))}",
    ]
    return lines


def _prompt_reference_receipt(stages: Sequence[StageReceipt]) -> StageReceipt | None:
    for receipt in stages:
        if receipt.stage == "prompt_reference_generation":
            return receipt
    return None


def _prompt_provider_quote(metrics: Mapping[str, Any]) -> Mapping[str, Any]:
    quote = metrics.get("provider_quote")
    return quote if isinstance(quote, Mapping) else {}


def _prompt_budget_status(receipt: StageReceipt) -> str:
    message = receipt.message.lower()
    quote = _prompt_provider_quote(receipt.metrics)
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
    if receipt.status.value == "succeeded":
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


__all__ = [
    "artifact_to_dict",
    "build_run_report_dict",
    "render_markdown_report",
    "stage_receipt_to_dict",
    "write_run_report",
]
