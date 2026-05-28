"""Home-page Final Readiness / Remaining Actions panel (read-only aggregation)."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any


def build_final_readiness_view(
    plan: Mapping[str, Any],
    *,
    physical_status: Mapping[str, Any] | None = None,
    feedback_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a UI view model from existing final-plan and status payloads."""

    sections = _as_dicts(plan.get("sections"))
    pillars = [
        _pillar_from_section(
            section,
            physical_status=physical_status,
            feedback_status=feedback_status,
        )
        for section in sections
    ]
    actions = [
        _action_item(section, action, index=index)
        for section in sections
        for index, action in enumerate(_as_dicts(section.get("actions")), start=1)
    ]
    next_action = _mapping(plan.get("next_action"))
    return {
        "overall_status": str(plan.get("overall_status") or "unknown"),
        "action_count": int(plan.get("action_count") or 0),
        "proof_boundary": str(plan.get("proof_boundary") or ""),
        "next_action": next_action,
        "pillars": pillars,
        "actions": actions,
    }


def render_final_readiness_panel(view: Mapping[str, Any]) -> str:
    """Render the consolidated final-readiness command-center panel."""

    overall = str(view.get("overall_status") or "unknown")
    action_count = str(view.get("action_count") or 0)
    proof_boundary = str(view.get("proof_boundary") or "")
    pillars = _as_dicts(view.get("pillars"))
    actions = _as_dicts(view.get("actions"))
    next_action = _mapping(view.get("next_action"))

    next_action_markup = ""
    if next_action:
        command = str(next_action.get("command") or "")
        next_action_file_markup = _render_next_action_files(next_action)
        next_action_markup = "\n".join(
            [
                '        <p class="final-readiness-next">',
                "          <strong>Next action:</strong> ",
                f"{escape(str(next_action.get('section_label') or ''))} · ",
                f"{escape(str(next_action.get('label') or ''))} — ",
                f"{escape(str(next_action.get('detail') or ''))}",
                "        </p>",
                (
                    f'        <pre><code>{escape(command)}</code></pre>'
                    if command
                    else ""
                ),
                next_action_file_markup,
            ]
        )

    pillar_cards = "\n".join(_render_pillar_card(pillar) for pillar in pillars)
    if not pillar_cards:
        pillar_cards = '<p class="muted">No final readiness pillars recorded.</p>'

    if actions:
        action_rows = "\n".join(_render_action_row(action) for action in actions)
        checklist = "\n".join(
            [
                '        <ol class="final-readiness-checklist">',
                action_rows,
                "        </ol>",
            ]
        )
    else:
        checklist = '<p class="muted">No remaining endgame actions recorded.</p>'

    return "\n".join(
        [
            '    <section class="panel final-readiness-panel">',
            "      <div>",
            '        <h2>Final readiness / Remaining actions</h2>',
            f'        <p class="muted">Overall: <strong>{escape(overall)}</strong>; '
            f"<strong>{escape(action_count)}</strong> remaining action(s).</p>",
            f"        <p class=\"final-readiness-boundary\">{escape(proof_boundary)}</p>",
            next_action_markup,
            "      </div>",
            f'      <div class="final-readiness-pillars">{pillar_cards}</div>',
            "      <div>",
            "        <h3>Remaining actions</h3>",
            checklist,
            "      </div>",
            '      <p class="muted final-readiness-links">'
            '        <a href="/final-plan.json">Final plan JSON</a> · '
            '        <a href="/physical-plan.json">Physical plan</a> · '
            '        <a href="/beta-feedback-plan.json">Trusted-user feedback plan</a> · '
            '        <a href="/release-plan.json">Release plan</a>',
            "      </p>",
            "    </section>",
        ]
    )


def _pillar_from_section(
    section: Mapping[str, Any],
    *,
    physical_status: Mapping[str, Any] | None,
    feedback_status: Mapping[str, Any] | None,
) -> dict[str, Any]:
    section_id = str(section.get("id") or "unknown")
    label = str(section.get("label") or section_id)
    status = str(section.get("status") or "unknown")
    action_count = int(section.get("action_count") or 0)
    command = str(section.get("command") or "")
    proof = str(section.get("proof_boundary") or "")

    if section_id == "physical_validation":
        headline = _physical_headline(physical_status)
        note = (
            "Digital coupons, meshes, and slice receipts are not physical proof. "
            "Incomplete or not-printed packets do not close this gate."
        )
    elif section_id == "trusted_user_beta":
        headline = _feedback_headline(feedback_status)
        note = (
            "Recorded not-run or incomplete feedback packets are visible for audit "
            "but do not count as completed beta feedback."
        )
    elif section_id == "release_distribution":
        headline = (
            f"{action_count} signing or distribution action(s) still open"
            if action_count
            else "Release distribution gates satisfied"
        )
        note = (
            "Unsigned build artifacts and generated plans are not distribution proof. "
            "macOS notarization and Windows Authenticode still required when applicable."
        )
    else:
        headline = str(section.get("detail") or "Final gate status unknown.")
        note = proof or "See section plan for proof boundaries."

    return {
        "id": section_id,
        "label": label,
        "status": status,
        "headline": headline,
        "note": note,
        "action_count": action_count,
        "command": command,
        "proof_boundary": proof,
    }


def _physical_headline(physical_status: Mapping[str, Any] | None) -> str:
    if not physical_status:
        return "Physical validation status unavailable"
    families = physical_status.get("family_status")
    if not isinstance(families, dict) or not families:
        required = physical_status.get("required_families")
        total = len(required) if isinstance(required, list) else 3
        return f"0/{total} material families have credible passed physical evidence"
    passed = sum(
        1
        for payload in families.values()
        if isinstance(payload, dict) and payload.get("status") == "passed"
    )
    total = len(families)
    return (
        f"{passed}/{total} material families have credible passed physical evidence"
    )


def _feedback_headline(feedback_status: Mapping[str, Any] | None) -> str:
    if not feedback_status:
        return "Trusted-user beta status unavailable"
    completed = int(feedback_status.get("completed_trusted_user_count") or 0)
    required = int(feedback_status.get("required_trusted_user_count") or 3)
    not_run = feedback_status.get("not_run_trusted_users")
    not_run_count = len(not_run) if isinstance(not_run, list) else 0
    headline = (
        f"{completed}/{required} trusted users with completed feedback packets"
    )
    if not_run_count:
        headline += f"; {not_run_count} not-run packet(s) recorded separately"
    return headline


def _action_item(
    section: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    section_id = str(section.get("id") or "unknown")
    section_label = str(section.get("label") or section_id)
    status = str(action.get("status") or section.get("status") or "action_required")
    return {
        "section_id": section_id,
        "section_label": section_label,
        "index": index,
        "status": status,
        "label": _action_label(action),
        "detail": _action_detail(action),
        "command": _action_command(action),
        "coupon_stl_path": str(action.get("coupon_stl_path") or ""),
        "coupon_json_path": str(action.get("coupon_json_path") or ""),
        "handoff_markdown_path": str(action.get("handoff_markdown_path") or ""),
    }


def _action_label(action: Mapping[str, Any]) -> str:
    family = action.get("family")
    if family:
        return f"{str(family).upper()} physical validation"
    slot = action.get("slot")
    if slot is not None:
        tester = action.get("tester")
        if tester:
            return f"Trusted-user feedback ({tester})"
        return f"Trusted-user feedback (tester slot {slot})"
    label = action.get("label") or action.get("id")
    if label:
        return str(label)
    return "Remaining action"


def _render_next_action_files(next_action: Mapping[str, Any]) -> str:
    rows = []
    file_labels = (
        ("coupon_stl_path", "Next action artifact"),
        ("coupon_json_path", "Next action sidecar"),
        ("handoff_markdown_path", "Next action handoff"),
        ("report_path", "Next action report"),
        ("bundle_path", "Next action bundle"),
    )
    for key, label in file_labels:
        value = str(next_action.get(key) or "")
        if value:
            rows.append(
                f'        <p class="muted">{escape(label)}: '
                f"<code>{escape(value)}</code></p>"
            )
    return "\n".join(rows)


def _action_detail(action: Mapping[str, Any]) -> str:
    for key in ("detail", "reason", "missing_reason"):
        value = action.get(key)
        if value:
            return str(value)
    required = action.get("required_fields")
    if isinstance(required, list) and required:
        return "Required: " + ", ".join(str(item) for item in required)
    return "Action still required before this gate can close."


def _action_command(action: Mapping[str, Any]) -> str:
    for key in (
        "start_command",
        "record_command",
        "command",
        "followup_command",
        "setup_command",
    ):
        value = action.get(key)
        if value:
            return str(value)
    return ""


def _render_pillar_card(pillar: Mapping[str, Any]) -> str:
    status = str(pillar.get("status") or "unknown")
    label = str(pillar.get("label") or "Gate")
    command = str(pillar.get("command") or "")
    command_markup = (
        f'          <pre><code>{escape(command)}</code></pre>'
        if command
        else ""
    )
    return "\n".join(
        [
            f'        <article class="final-readiness-pillar final-readiness-pillar-{_class_name(status)}">',
            f"          <span>{escape(label)}</span>",
            f"          <strong>{escape(status.replace('_', ' '))}</strong>",
            f"          <p>{escape(str(pillar.get('headline') or ''))}</p>",
            f'          <p class="muted">{escape(str(pillar.get("note") or ""))}</p>',
            f'          <p class="muted">{escape(str(pillar.get("action_count") or 0))} action(s) in this pillar.</p>',
            command_markup,
            "        </article>",
        ]
    )


def _render_action_row(action: Mapping[str, Any]) -> str:
    status = str(action.get("status") or "action_required")
    section_label = str(action.get("section_label") or "Action")
    label = str(action.get("label") or "Remaining action")
    detail = str(action.get("detail") or "")
    command = str(action.get("command") or "")
    coupon_stl_path = str(action.get("coupon_stl_path") or "")
    handoff_markdown_path = str(action.get("handoff_markdown_path") or "")
    command_markup = (
        f'            <pre><code>{escape(command)}</code></pre>'
        if command
        else ""
    )
    coupon_markup = (
        "            <p class=\"muted\">Coupon artifact: "
        f"<code>{escape(coupon_stl_path)}</code></p>"
        if coupon_stl_path
        else ""
    )
    handoff_markup = (
        "            <p class=\"muted\">Handoff: "
        f"<code>{escape(handoff_markdown_path)}</code></p>"
        if handoff_markdown_path
        else ""
    )
    return "\n".join(
        [
            f'          <li class="final-readiness-action final-readiness-action-{_class_name(status)}">',
            f'            <p class="action-title"><strong>{escape(section_label)}</strong> · {escape(label)}</p>',
            f'            <p class="muted">{escape(detail)}</p>',
            coupon_markup,
            handoff_markup,
            command_markup,
            "          </li>",
        ]
    )


def _class_name(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value.lower())


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


__all__ = ["build_final_readiness_view", "render_final_readiness_panel"]
