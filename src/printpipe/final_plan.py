"""Final action plan for the remaining PrintPipe release gates."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from printpipe.beta.feedback import build_trusted_user_feedback_plan
from printpipe.beta.physical_plan import build_physical_validation_plan
from printpipe.packaging.release_plan import build_release_distribution_plan

FINAL_PLAN_PROOF_BOUNDARY = (
    "A final plan is not evidence. Physical validation, trusted-user beta, "
    "and signed distribution gates only close when their underlying evidence "
    "packets or verified signed artifacts exist on disk."
)


def build_final_action_plan(
    *,
    runs_dir: str | Path,
    release_dir: str | Path,
    regression_manifest_path: str | Path | None = None,
    physical_plan: Mapping[str, Any] | None = None,
    trusted_feedback_plan: Mapping[str, Any] | None = None,
    release_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the ordered endgame checklist for the remaining external gates."""

    runs_path = Path(runs_dir).expanduser()
    release_path = Path(release_dir).expanduser()
    physical = dict(physical_plan) if physical_plan is not None else build_physical_validation_plan(runs_path)
    trusted = (
        dict(trusted_feedback_plan)
        if trusted_feedback_plan is not None
        else build_trusted_user_feedback_plan(runs_path)
    )
    release = (
        dict(release_plan)
        if release_plan is not None
        else build_release_distribution_plan(
            release_dir=release_path,
            runs_dir=runs_path,
            regression_manifest_path=regression_manifest_path,
        )
    )
    sections = [
        _section(
            "physical_validation",
            "Physical validation",
            physical,
            detail="Print and record PLA, PETG, and TPU coupon or small-object evidence.",
            command=f"printpipe physical-plan --runs-dir {_quote(str(runs_path))}",
        ),
        _section(
            "trusted_user_beta",
            "Trusted-user beta",
            trusted,
            detail="Give trusted users real runs to review and record their feedback packets.",
            command=f"printpipe beta-feedback-plan --runs-dir {_quote(str(runs_path))}",
        ),
        _section(
            "release_distribution",
            "Release distribution",
            release,
            detail="Build, sign, notarize, and verify the final macOS and Windows artifacts.",
            command=_release_plan_command(
                release_dir=release_path,
                runs_dir=runs_path,
                regression_manifest_path=regression_manifest_path,
            ),
        ),
    ]
    action_count = sum(int(section["action_count"]) for section in sections)
    return {
        "schema_version": 1,
        "runs_dir": str(runs_path),
        "release_dir": str(release_path),
        "regression_manifest_path": (
            str(regression_manifest_path) if regression_manifest_path is not None else ""
        ),
        "overall_status": "ready" if action_count == 0 else "action_required",
        "action_count": action_count,
        "proof_boundary": FINAL_PLAN_PROOF_BOUNDARY,
        "sections": sections,
    }


def render_final_action_plan(plan: Mapping[str, Any]) -> str:
    """Render the final action plan for terminal use."""

    lines = [
        "PrintPipe Final Action Plan",
        f"overall: {plan.get('overall_status', 'unknown')}",
        f"action required: {plan.get('action_count', 0)}",
        f"runs dir: {plan.get('runs_dir', '')}",
        f"release dir: {plan.get('release_dir', '')}",
        "",
        str(plan.get("proof_boundary", FINAL_PLAN_PROOF_BOUNDARY)),
        "",
        "Sections:",
    ]
    sections = _list(plan.get("sections"))
    if not sections:
        lines.append("- no final-plan sections recorded")
        return "\n".join(lines) + "\n"
    for section_value in sections:
        section = _dict(section_value)
        lines.append(
            f"- {section.get('status', 'unknown')}: "
            f"{section.get('id', 'unknown')} - {section.get('label', '')} "
            f"({section.get('action_count', 0)} action required)"
        )
        detail = str(section.get("detail") or "")
        if detail:
            lines.append(f"  detail: {detail}")
        boundary = str(section.get("proof_boundary") or "")
        if boundary:
            lines.append(f"  proof: {boundary}")
        command = str(section.get("command") or "")
        if command:
            lines.append(f"  command: {command}")
        for action in _list(section.get("actions")):
            summary = _action_summary(_dict(action))
            if summary:
                lines.append(f"  - {summary}")
    return "\n".join(lines) + "\n"


def _section(
    section_id: str,
    label: str,
    source_plan: Mapping[str, Any],
    *,
    detail: str,
    command: str,
) -> dict[str, Any]:
    action_count = _action_count(source_plan)
    return {
        "id": section_id,
        "label": label,
        "status": "ready" if action_count == 0 else "action_required",
        "source_status": str(source_plan.get("overall_status") or "unknown"),
        "action_count": action_count,
        "detail": detail,
        "command": command,
        "proof_boundary": str(source_plan.get("proof_boundary") or ""),
        "actions": _list(source_plan.get("actions")),
    }


def _action_count(source_plan: Mapping[str, Any]) -> int:
    raw_count = source_plan.get("action_count")
    if isinstance(raw_count, int):
        return max(raw_count, 0)
    return len(_list(source_plan.get("actions")))


def _release_plan_command(
    *,
    release_dir: Path,
    runs_dir: Path,
    regression_manifest_path: str | Path | None,
) -> str:
    command = (
        "printpipe release-plan --release-dir "
        f"{_quote(str(release_dir))} --runs-dir {_quote(str(runs_dir))}"
    )
    if regression_manifest_path is not None:
        command += f" --regression-manifest {_quote(str(regression_manifest_path))}"
    return command


def _action_summary(action: Mapping[str, Any]) -> str:
    label = action.get("label") or action.get("id") or action.get("family")
    if label is None and action.get("slot") is not None:
        label = f"tester slot {action.get('slot')}"
    status = action.get("status")
    if label is None and status is None:
        return ""
    if status is None:
        return str(label)
    return f"{status}: {label}"


def _quote(value: str) -> str:
    return shlex.quote(value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "FINAL_PLAN_PROOF_BOUNDARY",
    "build_final_action_plan",
    "render_final_action_plan",
]
