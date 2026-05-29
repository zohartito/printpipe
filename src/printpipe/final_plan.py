"""Final action plan for the remaining PrintPipe release gates."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from printpipe.beta.feedback import build_trusted_user_feedback_plan
from printpipe.beta.physical_plan import build_physical_validation_plan
from printpipe.meshgen.providers import HUNYUAN3D_COMMAND_ENV, MEDIA_MESHGEN_COMMAND_ENV
from printpipe.env.doctor import build_environment_report
from printpipe.meshgen.smoke import build_media_meshgen_smoke_status
from printpipe.packaging.release_plan import build_release_distribution_plan

FINAL_PLAN_PROOF_BOUNDARY = (
    "A final plan is not evidence. Media meshgen, physical validation, "
    "trusted-user beta, and signed distribution gates only close when their "
    "underlying smoke receipts, evidence packets, or verified signed artifacts "
    "exist on disk."
)

MEDIA_MESHGEN_PROOF_BOUNDARY = (
    "A configured media meshgen command is not proof. This gate closes only "
    "after a successful media-meshgen-smoke receipt points at an existing "
    "output mesh."
)


def build_final_action_plan(
    *,
    runs_dir: str | Path,
    release_dir: str | Path,
    regression_manifest_path: str | Path | None = None,
    physical_plan: Mapping[str, Any] | None = None,
    media_meshgen_plan: Mapping[str, Any] | None = None,
    trusted_feedback_plan: Mapping[str, Any] | None = None,
    release_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the ordered endgame checklist for the remaining external gates."""

    runs_path = Path(runs_dir).expanduser()
    release_path = Path(release_dir).expanduser()
    media = (
        dict(media_meshgen_plan)
        if media_meshgen_plan is not None
        else build_media_meshgen_action_plan(runs_path)
    )
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
            "media_meshgen_provider",
            "Media meshgen provider",
            media,
            detail="Configure and smoke-prove the image/GIF/video meshgen provider.",
            command=(
                "printpipe media-meshgen-smoke-status --runs-dir "
                f"{_quote(str(runs_path))} --strict"
            ),
        ),
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
    next_action = _next_action(sections)
    return {
        "schema_version": 1,
        "runs_dir": str(runs_path),
        "release_dir": str(release_path),
        "regression_manifest_path": (
            str(regression_manifest_path) if regression_manifest_path is not None else ""
        ),
        "overall_status": "ready" if action_count == 0 else "action_required",
        "action_count": action_count,
        "next_action": next_action,
        "next_command": str(next_action.get("command") or ""),
        "proof_boundary": FINAL_PLAN_PROOF_BOUNDARY,
        "sections": sections,
    }


def build_media_meshgen_action_plan(
    runs_dir: str | Path,
    *,
    environment_report: Mapping[str, Any] | None = None,
    smoke_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return final-plan actions for media meshgen provider proof."""

    runs_path = Path(runs_dir).expanduser()
    environment = (
        dict(environment_report)
        if environment_report is not None
        else build_environment_report()
    )
    smoke = (
        dict(smoke_status)
        if smoke_status is not None
        else build_media_meshgen_smoke_status(runs_path)
    )
    meshgen = _dict(environment.get("meshgen"))
    if meshgen.get("overall_status") != "ready":
        tested_command_action = _tested_media_command_action(
            runs_path=runs_path,
            smoke_status=smoke,
            detail=str(
                meshgen.get("message")
                or meshgen.get("action")
                or "No live image/GIF/video meshgen provider is configured."
            ),
        )
        if tested_command_action is not None:
            return _media_meshgen_plan(
                overall_status="action_required",
                action=tested_command_action,
                provider_count=int(meshgen.get("live_media_provider_count") or 0),
                smoke_status=smoke,
            )
        action = {
            "id": "configure_media_meshgen_provider",
            "label": "Configure media meshgen provider",
            "status": "action_required",
            "detail": str(
                meshgen.get("message")
                or meshgen.get("action")
                or "No live image/GIF/video meshgen provider is configured."
            ),
            "start_command": "printpipe media-meshgen-template --output scripts/media_meshgen_adapter.py",
            "command": (
                "printpipe media-meshgen-smoke reference.png --runs-dir "
                f"{_quote(str(runs_path))}"
            ),
            "followup_command": (
                "printpipe media-meshgen-smoke-status --runs-dir "
                f"{_quote(str(runs_path))} --strict"
            ),
            "required_inputs": [
                "real local, hosted, or API-backed media meshgen adapter",
                "image, GIF, or video reference for smoke testing",
            ],
            "input_type": "image/GIF/video",
        }
        return _media_meshgen_plan(
            overall_status="action_required",
            action=action,
            provider_count=int(meshgen.get("live_media_provider_count") or 0),
            smoke_status=smoke,
        )

    if smoke.get("overall_status") != "passed":
        action = {
            "id": "media_meshgen_smoke",
            "label": "Media meshgen smoke",
            "status": str(smoke.get("overall_status") or "missing"),
            "detail": str(
                smoke.get("message")
                or "Configured provider has no successful media meshgen smoke receipt."
            ),
            "command": (
                "printpipe media-meshgen-smoke reference.png --runs-dir "
                f"{_quote(str(runs_path))}"
            ),
            "followup_command": (
                "printpipe media-meshgen-smoke-status --runs-dir "
                f"{_quote(str(runs_path))} --strict"
            ),
            "required_inputs": ["image, GIF, or video reference"],
            "input_type": "image/GIF/video",
        }
        return _media_meshgen_plan(
            overall_status="action_required",
            action=action,
            provider_count=int(meshgen.get("live_media_provider_count") or 0),
            smoke_status=smoke,
        )

    return _media_meshgen_plan(
        overall_status="ready",
        action=None,
        provider_count=int(meshgen.get("live_media_provider_count") or 0),
        smoke_status=smoke,
    )


def _tested_media_command_action(
    *,
    runs_path: Path,
    smoke_status: Mapping[str, Any],
    detail: str,
) -> dict[str, Any] | None:
    if smoke_status.get("overall_status") != "passed":
        return None
    latest = _dict(smoke_status.get("latest_successful_smoke"))
    command = str(latest.get("command") or "").strip()
    if not command:
        return None
    provider_id = str(latest.get("provider_id") or "")
    env_name = (
        HUNYUAN3D_COMMAND_ENV
        if provider_id == "hunyuan3d"
        else MEDIA_MESHGEN_COMMAND_ENV
    )
    run_id = str(latest.get("run_id") or "latest successful smoke")
    return {
        "id": "configure_tested_media_meshgen_provider",
        "label": "Configure tested media meshgen command",
        "status": "action_required",
        "detail": (
            f"{detail} Latest successful smoke {run_id} used a command that can "
            f"be exported as {env_name}."
        ),
        "start_command": f"export {env_name}={_quote(command)}",
        "command": (
            "printpipe media-meshgen-smoke reference.png --runs-dir "
            f"{_quote(str(runs_path))}"
        ),
        "followup_command": (
            "printpipe media-meshgen-smoke-status --runs-dir "
            f"{_quote(str(runs_path))} --strict"
        ),
        "required_inputs": [
            "shell session, launch agent, or app environment where the export is set",
            "image, GIF, or video reference for a fresh configured-provider smoke",
        ],
        "input_type": "image/GIF/video",
        "latest_successful_smoke_run_id": run_id,
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
    ]
    next_action = _dict(plan.get("next_action"))
    if next_action:
        lines.extend(
            [
                "Next action:",
                (
                    f"- {next_action.get('section_label', '')}: "
                    f"{next_action.get('label', '')} "
                    f"({next_action.get('status', 'unknown')})"
                ),
            ]
        )
        detail = str(next_action.get("detail") or "")
        if detail:
            lines.append(f"  detail: {detail}")
        command = str(next_action.get("command") or "")
        if command:
            lines.append(f"  command: {command}")
        for label, value in _supporting_info_lines(next_action):
            lines.append(f"  {label}: {value}")
        for label, value in _supporting_command_lines(next_action):
            lines.append(f"  {label}: {value}")
        for label, value in _supporting_path_lines(next_action):
            lines.append(f"  {label}: {value}")
        lines.append("")
    lines.append("Sections:")
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
            for action_line in _section_action_lines(_dict(action), section):
                lines.append(f"  {action_line}")
    return "\n".join(lines) + "\n"


def build_final_next_action_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the focused next-action payload from a full final action plan."""

    next_action = _dict(plan.get("next_action"))
    return {
        "schema_version": int(plan.get("schema_version") or 1),
        "overall_status": str(plan.get("overall_status") or "unknown"),
        "action_count": int(plan.get("action_count") or 0),
        "proof_boundary": str(plan.get("proof_boundary") or FINAL_PLAN_PROOF_BOUNDARY),
        "next_action": next_action,
        "next_command": str(plan.get("next_command") or next_action.get("command") or ""),
    }


def render_final_next_action(plan: Mapping[str, Any]) -> str:
    """Render only the immediate next action from a final action plan."""

    next_action = _dict(plan.get("next_action"))
    lines = [
        "PrintPipe Final Next Action",
        f"overall: {plan.get('overall_status', 'unknown')}",
        f"action required: {plan.get('action_count', 0)}",
        "",
        str(plan.get("proof_boundary", FINAL_PLAN_PROOF_BOUNDARY)),
        "",
    ]
    if not next_action:
        lines.append("No next action recorded.")
        return "\n".join(lines) + "\n"

    lines.append(
        (
            f"{next_action.get('section_label', '')}: "
            f"{next_action.get('label', '')} "
            f"({next_action.get('status', 'unknown')})"
        )
    )
    detail = str(next_action.get("detail") or "")
    if detail:
        lines.append(f"detail: {detail}")
    command = str(next_action.get("command") or "")
    if command:
        lines.append(f"command: {command}")
    for label, value in _supporting_info_lines(next_action):
        lines.append(f"{label}: {value}")
    for label, value in _supporting_command_lines(next_action):
        lines.append(f"{label}: {value}")
    for label, value in _supporting_path_lines(next_action):
        lines.append(f"{label}: {value}")
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


def _media_meshgen_plan(
    *,
    overall_status: str,
    action: Mapping[str, Any] | None,
    provider_count: int,
    smoke_status: Mapping[str, Any],
) -> dict[str, Any]:
    actions = [dict(action)] if action is not None else []
    return {
        "schema_version": 1,
        "overall_status": overall_status,
        "action_count": len(actions),
        "provider_count": provider_count,
        "smoke_status": dict(smoke_status),
        "proof_boundary": MEDIA_MESHGEN_PROOF_BOUNDARY,
        "actions": actions,
    }


def _supporting_path_lines(action: Mapping[str, Any]) -> list[tuple[str, str]]:
    pairs = (
        ("coupon_stl_path", "artifact"),
        ("coupon_json_path", "sidecar"),
        ("handoff_markdown_path", "handoff"),
        ("report_path", "report"),
        ("bundle_path", "bundle"),
        ("bundle_validation_path", "bundle validation"),
        ("slice_result_path", "slice"),
    )
    lines: list[tuple[str, str]] = []
    for key, label in pairs:
        value = str(action.get(key) or "")
        if value:
            lines.append((label, value))
    return lines


def _supporting_info_lines(action: Mapping[str, Any]) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    context = _evidence_context_text(action)
    if context:
        lines.append(("evidence context", context))
    required = _list(action.get("required_inputs"))
    if required:
        lines.append(("required inputs", ", ".join(str(item) for item in required)))
    required_fields = _list(action.get("required_fields"))
    if required_fields:
        lines.append(("required fields", ", ".join(str(item) for item in required_fields)))
    return lines


def _supporting_command_lines(action: Mapping[str, Any]) -> list[tuple[str, str]]:
    immediate = str(action.get("command") or "")
    setup = str(action.get("setup_command") or "")
    run = str(action.get("run_command") or "")
    followup = str(action.get("followup_command") or "")
    record = str(action.get("record_command") or "")
    lines: list[tuple[str, str]] = []
    if setup and setup != immediate:
        lines.append(("setup prerequisite", setup))
    if run and run not in {immediate, setup}:
        lines.append(("run after prerequisites", run))
    if followup and followup not in {immediate, run}:
        lines.append(("follow-up check", followup))
    if record and record != immediate:
        label = (
            "record after review"
            if str(action.get("section_id") or "") == "trusted_user_beta"
            else "record after print"
        )
        lines.append((label, record))
    return lines


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
    label = _action_label(action)
    status = action.get("status")
    if label is None and status is None:
        return ""
    if status is None:
        return str(label)
    return f"{status}: {label}"


def _section_action_lines(
    action: Mapping[str, Any],
    section: Mapping[str, Any],
) -> list[str]:
    summary = _action_summary(action)
    if not summary:
        return []
    lines = [f"- {summary}"]
    detail = _action_detail(action, section)
    if detail:
        lines.append(f"  detail: {detail}")
    for label, value in _supporting_info_lines(action):
        lines.append(f"  {label}: {value}")
    for label, value in _section_action_command_lines(action, section):
        lines.append(f"  {label}: {value}")
    for label, value in _supporting_path_lines(action):
        lines.append(f"  {label}: {value}")
    return lines


def _section_action_command_lines(
    action: Mapping[str, Any],
    section: Mapping[str, Any],
) -> list[tuple[str, str]]:
    section_id = str(section.get("id") or "")
    lines: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, label in (
        ("start_command", "start"),
        ("setup_command", "setup"),
        ("command", "command"),
        ("followup_command", "follow-up check"),
    ):
        command = str(action.get(key) or "")
        if command and command not in seen:
            lines.append((label, command))
            seen.add(command)
    record = str(action.get("record_command") or "")
    if record and record not in seen:
        if (
            section_id != "trusted_user_beta"
            and (action.get("start_command") or action.get("setup_command"))
        ):
            return lines
        label = (
            "record after review"
            if section_id == "trusted_user_beta"
            else "record after print"
        )
        lines.append((label, record))
    return lines


def _next_action(sections: list[dict[str, Any]]) -> dict[str, Any]:
    for section in sections:
        if int(section.get("action_count") or 0) <= 0:
            continue
        actions = _list(section.get("actions"))
        if not actions:
            return _section_as_next_action(section)
        action = _dict(actions[0])
        if not action:
            return _section_as_next_action(section)
        command_kind, command = _action_command(action, section)
        payload = {
            "section_id": str(section.get("id") or ""),
            "section_label": str(section.get("label") or ""),
            "action_id": _action_id(action),
            "label": _action_label(action),
            "status": str(action.get("status") or section.get("status") or "unknown"),
            "detail": _action_detail(action, section),
            "command": command,
            "command_kind": command_kind,
        }
        for key in (
            "coupon_stl_path",
            "coupon_json_path",
            "handoff_markdown_path",
            "report_path",
            "bundle_path",
            "bundle_validation_path",
            "slice_result_path",
            "run_root",
            "material_hint",
            "material",
            "printer",
            "object_label",
            "print_type",
            "input_type",
            "tester",
        ):
            value = str(action.get(key) or "")
            if value:
                payload[key] = value
        required_inputs = _list(action.get("required_inputs"))
        if required_inputs:
            payload["required_inputs"] = [str(item) for item in required_inputs]
        required_fields = _list(action.get("required_fields"))
        if required_fields:
            payload["required_fields"] = [str(item) for item in required_fields]
        run_command = _run_command(action, immediate_command=command)
        setup_command = str(action.get("setup_command") or "")
        if setup_command and setup_command != command:
            payload["setup_command"] = setup_command
        if run_command:
            payload["run_command"] = run_command
        followup_command = str(action.get("followup_command") or "")
        if followup_command and followup_command not in {command, run_command}:
            payload["followup_command"] = followup_command
        record_command = str(action.get("record_command") or "")
        if (
            record_command
            and record_command != command
            and (
                command_kind not in {"start_command", "setup_command"}
                or str(section.get("id") or "") == "trusted_user_beta"
            )
        ):
            payload["record_command"] = record_command
        return payload
    return {}


def _section_as_next_action(section: Mapping[str, Any]) -> dict[str, Any]:
    command = str(section.get("command") or "")
    return {
        "section_id": str(section.get("id") or ""),
        "section_label": str(section.get("label") or ""),
        "action_id": str(section.get("id") or ""),
        "label": str(section.get("label") or "Next gate"),
        "status": str(section.get("status") or "unknown"),
        "detail": str(section.get("detail") or ""),
        "command": command,
        "command_kind": "section_command" if command else "",
    }


def _action_command(
    action: Mapping[str, Any],
    section: Mapping[str, Any],
) -> tuple[str, str]:
    for key in (
        "start_command",
        "command",
        "record_command",
        "setup_command",
        "followup_command",
    ):
        command = str(action.get(key) or "")
        if command:
            if key == "command":
                return str(action.get("command_kind") or key), command
            return key, command
    command = str(section.get("command") or "")
    if command:
        return "section_command", command
    return "", ""


def _run_command(action: Mapping[str, Any], *, immediate_command: str) -> str:
    command = str(action.get("command") or "")
    if not command or command == immediate_command:
        return ""
    return command


def _action_id(action: Mapping[str, Any]) -> str:
    if action.get("id") is not None:
        return str(action.get("id"))
    if action.get("family") is not None:
        return str(action.get("family"))
    if action.get("slot") is not None:
        return f"trusted-user-{action.get('slot')}"
    return str(action.get("label") or "next-action")


def _action_label(action: Mapping[str, Any]) -> str:
    if action.get("label") is not None:
        return str(action.get("label"))
    if action.get("family") is not None:
        return str(action.get("family")).upper()
    if action.get("slot") is not None:
        return f"Trusted tester {action.get('slot')}"
    if action.get("id") is not None:
        return str(action.get("id"))
    return "Next action"


def _action_detail(
    action: Mapping[str, Any],
    section: Mapping[str, Any],
) -> str:
    return str(
        action.get("detail")
        or action.get("reason")
        or section.get("detail")
        or ""
    )


def _evidence_context_text(action: Mapping[str, Any]) -> str:
    pairs = (
        ("material_hint", "Material"),
        ("material", "Material"),
        ("printer", "Printer"),
        ("object_label", "Object"),
        ("print_type", "Print type"),
        ("input_type", "Input"),
        ("tester", "Tester"),
        ("run_root", "Run"),
    )
    seen_labels: set[str] = set()
    parts: list[str] = []
    for key, label in pairs:
        value = str(action.get(key) or "")
        if not value or label in seen_labels:
            continue
        seen_labels.add(label)
        parts.append(f"{label}: {value}")
    return "; ".join(parts)


def _quote(value: str) -> str:
    return shlex.quote(value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "FINAL_PLAN_PROOF_BOUNDARY",
    "MEDIA_MESHGEN_PROOF_BOUNDARY",
    "build_final_action_plan",
    "build_final_next_action_payload",
    "build_media_meshgen_action_plan",
    "render_final_action_plan",
    "render_final_next_action",
]
