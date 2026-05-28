"""Server-rendered run-detail workbench UI."""

from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote


def render_run_detail_page(*, detail: dict[str, Any], artifact_links: list[Any]) -> str:
    run_id = str(detail.get("run_id", "unknown-run"))
    verdict = _mapping(detail.get("print_verdict"))
    status_label = str(verdict.get("label") or "Review before print")
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>PrintPipe Workbench: {escape(run_id)}</title>",
            f"  <style>{RUN_DETAIL_CSS}</style>",
            "</head>",
            "<body>",
            '  <main class="app run-detail-app">',
            '    <header class="topbar">',
            "      <div>",
            '        <p class="eyebrow"><a href="/">PrintPipe</a> / Model workbench</p>',
            f"        <h1>{escape(run_id)}</h1>",
            f'        <div class="run-meta">{_render_run_meta(detail)}</div>',
            "      </div>",
            (
                f'      <div class="status-chip status-chip-{escape(_state_tone(str(verdict.get("state", "review"))), quote=True)}">'
                f"{escape(status_label)}</div>"
            ),
            "    </header>",
            '    <section class="shell">',
            _render_verdict_strip(detail),
            _render_run_context_strip(detail),
            _render_material_preflight_strip(detail, artifact_links),
            _render_prompt_provider_panel(detail),
            _render_physical_evidence_panel(detail),
            _render_model_workbench(detail, artifact_links),
            "    </section>",
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _render_run_meta(detail: dict[str, Any]) -> str:
    input_info = _mapping(detail.get("input"))
    parts = [
        f"input: {input_info.get('kind', 'unknown')}",
        str(_mapping(detail.get("printer")).get("label") or "printer pending"),
        str(_mapping(detail.get("material")).get("label") or "material pending"),
        str(_mapping(detail.get("profile")).get("label") or "profile pending"),
    ]
    return "".join(f"<span>{escape(part)}</span>" for part in parts if part)


def _render_verdict_strip(detail: dict[str, Any]) -> str:
    verdict = _mapping(detail.get("print_verdict"))
    tone = _state_tone(str(verdict.get("state", "review")))
    issue = _fit_issue_label(detail)
    checks = _validation_by_key(detail)
    cards = "\n".join(
        _render_score_card(label, checks.get(key))
        for label, key in (
            ("Manifold", "manifold"),
            ("Bed fit", "bed_fit"),
            ("TPU profile", "material_profile"),
            ("Support", "support_risk"),
            ("Slice", "slice_success"),
        )
    )
    return "\n".join(
        [
            f'      <section class="verdict-strip verdict-strip-{escape(tone, quote=True)}" aria-label="Can this run print?">',
            '        <article class="verdict">',
            '          <p class="eyebrow">Can this run print?</p>',
            f"          <h2>{escape(_verdict_heading(detail))}</h2>",
            f'          <strong class="verdict-issue">{escape(issue)}</strong>',
            f"          <p>{escape(_verdict_reason(detail))}</p>",
            f'          <p class="next-action"><span>Next action</span>{escape(_next_action_label(detail))}</p>',
            "        </article>",
            cards,
            "      </section>",
        ]
    )


def _render_score_card(label: str, check: dict[str, Any] | None) -> str:
    check = check or {"state": "review", "detail": "No check result yet."}
    state = str(check.get("state", "review"))
    tone = _state_tone(state)
    return "\n".join(
        [
            f'        <article class="score score-{escape(tone, quote=True)}">',
            f"          <span>{escape(label)}</span>",
            f"          <strong>{escape(_state_label(state))}</strong>",
            f'          <p>{escape(str(check.get("detail", "No check result yet.")))}</p>',
            "        </article>",
        ]
    )


def _render_run_context_strip(detail: dict[str, Any]) -> str:
    parent_run = _mapping(detail.get("parent_run"))
    items = [
        ("Input", str(_mapping(detail.get("input")).get("kind", "unknown"))),
        ("Bounds", _format_bounds(_mapping(detail.get("geometry")).get("bounds_mm"))),
        ("Warnings", str(len(_as_list(detail.get("warnings"))))),
    ]
    if parent_run:
        items.insert(0, ("Parent run", str(parent_run.get("run_id", "unknown"))))
        items.append(("Edit delta", _edit_delta_summary(detail)))
    items.append(("First warning", _first_warning(detail)))
    return _key_value_strip("run-context", "Run context", items)


def _render_material_preflight_strip(detail: dict[str, Any], artifact_links: list[Any]) -> str:
    items = [
        ("Printer", _label_from_detail(detail, "printer", "Printer not recorded")),
        ("Material", _label_from_detail(detail, "material", "Material not recorded")),
        ("Profile", _label_from_detail(detail, "profile", "Profile not recorded")),
        ("Use case", _use_case_label(detail)),
        ("Flex coupon", _flex_coupon_status(detail, artifact_links)),
        ("User-only gate", _physical_gate_status(detail)),
    ]
    return _key_value_strip("print-context", "Material and preflight context", items)


def _render_physical_evidence_panel(detail: dict[str, Any]) -> str:
    evidence = _mapping(detail.get("physical_evidence"))
    if not evidence.get("available"):
        return ""
    run_id = str(detail.get("run_id", "unknown-run"))
    packet_paths = _mapping(evidence.get("packet_paths"))
    packet_links = "".join(
        _physical_link(run_id, label, path)
        for label, path in (
            ("Evidence JSON", packet_paths.get("json")),
            ("Evidence Markdown", packet_paths.get("markdown")),
        )
        if path
    )
    artifact_links = "".join(
        _physical_link(
            run_id,
            str(artifact.get("label") or "Physical artifact"),
            artifact.get("path"),
        )
        for artifact in _as_dicts(evidence.get("artifacts"))
        if artifact.get("path")
    )
    missing = [str(item) for item in _as_list(evidence.get("missing_required_evidence"))]
    missing_label = (
        "No missing required evidence"
        if not missing
        else "Missing: " + ", ".join(missing)
    )
    return "\n".join(
        [
            '      <section class="physical-evidence" aria-label="Physical evidence">',
            "        <div>",
            "          <p class=\"eyebrow\">Physical evidence</p>",
            f"          <h2>{escape(_physical_evidence_heading(evidence))}</h2>",
            f"          <p>Operator: {escape(str(evidence.get('operator') or 'unrecorded'))}</p>",
            f'          <p class="evidence-missing">{escape(missing_label)}</p>',
            "        </div>",
            f'        <div class="evidence-links">{packet_links}{artifact_links}</div>',
            "      </section>",
        ]
    )


def _render_prompt_provider_panel(detail: dict[str, Any]) -> str:
    prompt_reference = _mapping(detail.get("prompt_reference"))
    if not prompt_reference.get("available"):
        return ""
    budget_status = _prompt_budget_status_label(prompt_reference)
    items = [
        ("Provider", _prompt_provider_label(prompt_reference.get("provider"))),
        ("Privacy", _privacy_mode_label(prompt_reference.get("privacy_mode"))),
        ("Estimated cost", _format_money(prompt_reference.get("estimated_cost_usd"))),
        ("Max cost", _format_money(prompt_reference.get("max_cost_usd"))),
        ("Latency", _format_seconds(prompt_reference.get("estimated_seconds"))),
        ("Budget", budget_status),
    ]
    remote_note = _remote_prompt_note(prompt_reference)
    return "\n".join(
        [
            '      <section class="prompt-provider" aria-label="Prompt image provider">',
            "        <div>",
            '          <p class="eyebrow">Prompt image provider</p>',
            f"          <h2>{escape(_prompt_provider_heading(prompt_reference))}</h2>",
            f"          <p>{escape(str(prompt_reference.get('stage_message') or 'No provider message recorded.'))}</p>",
            f'          <p class="provider-note">{escape(remote_note)}</p>',
            "        </div>",
            f'        <div class="provider-grid">{_render_provider_items(items)}</div>',
            "      </section>",
        ]
    )


def _render_model_workbench(detail: dict[str, Any], artifact_links: list[Any]) -> str:
    return "\n".join(
        [
            '      <section class="workbench">',
            '        <div class="canvas-zone">',
            _render_model_card(detail, artifact_links),
            '          <div class="lower-grid">',
            _render_stage_panel("Pipeline Stages", _as_dicts(detail.get("pipeline"))),
            _render_stage_panel("Validation Results", _as_dicts(detail.get("validation"))),
            "          </div>",
            _render_warning_receipts(detail),
            "        </div>",
            _render_edit_geometry_panel(str(detail.get("run_id", "unknown-run")), detail, artifact_links),
            "      </section>",
        ]
    )


def _render_model_card(detail: dict[str, Any], artifact_links: list[Any]) -> str:
    preview_links = [link for link in artifact_links if str(getattr(link, "category", "")) == "preview"]
    validation = _validation_by_key(detail)
    geometry = _mapping(detail.get("geometry"))
    return "\n".join(
        [
            '          <article class="model-card" aria-label="Model workbench">',
            '            <div class="toolbar"><div class="view-tabs" aria-label="Preview modes">',
            '              <span class="tab active" aria-current="true">Model</span><span class="tab">Bed Fit</span><span class="tab">Upper Fit</span><span class="tab">Support Risk</span><span class="tab">Slice</span>',
            f'            </div><p class="eyebrow">{escape(_artifact_primary_label(artifact_links))}</p></div>',
            _render_preview(preview_links, detail),
            '            <div class="model-footer">',
            _render_metric("Mesh", _state_label(str(validation.get("manifold", {}).get("state", "review")))),
            _render_metric("Bounds", _format_bounds(geometry.get("bounds_mm"))),
            _render_metric("Fit issue", _fit_issue_label(detail)),
            _render_metric("Slice gate", _state_label(str(validation.get("slice_success", {}).get("state", "review")))),
            "            </div>",
            _render_workbench_artifacts(str(detail.get("run_id", "unknown-run")), artifact_links),
            "          </article>",
        ]
    )


def _render_preview(preview_links: list[Any], detail: dict[str, Any]) -> str:
    geometry = _mapping(detail.get("geometry"))
    primary = _primary_model_preview(preview_links)
    title = str(getattr(primary, "label", "Model preview pending")) if primary else "Model preview pending"
    visual = (
        f'              <img class="model-preview-image" src="{escape(str(getattr(primary, "href", "")), quote=True)}" alt="{escape(title, quote=True)}">'
        if primary
        else '              <div class="mesh-placeholder"></div>'
    )
    links = "".join(
        f'<a href="{escape(str(getattr(link, "href", "#")), quote=True)}">{escape(str(getattr(link, "label", "Preview")))}</a>'
        for link in preview_links[:3]
    )
    return "\n".join(
        [
            '            <figure class="model-view" aria-label="Model preview">',
            '              <div class="bed"></div>',
            visual,
            f'              <figcaption class="preview-title">{escape(title)}</figcaption>',
            f'              <figcaption class="risk-marker">opening risk: {escape(str(geometry.get("support_risk") or "review").title())}</figcaption>',
            f'              <figcaption class="measure measure-x">{escape(_format_bounds(geometry.get("bounds_mm")))}</figcaption>',
            f'              <figcaption class="measure measure-z">{escape(_format_metric(geometry.get("print_time_minutes"), "min"))}</figcaption>',
            "            </figure>",
            f'            <div class="preview-links">{links}</div>' if links else "",
        ]
    )


def _render_workbench_artifacts(run_id: str, artifact_links: list[Any]) -> str:
    return "\n".join(
        [
            '            <section class="workbench-artifacts" aria-label="Primary artifacts">',
            '              <div class="artifact-heading"><h3>Artifacts</h3><p>Open the files you need while editing this run.</p></div>',
            _render_artifact_tiles(artifact_links),
            _render_open_folder_actions(run_id),
            "            </section>",
        ]
    )


def _render_edit_geometry_panel(run_id: str, detail: dict[str, Any], artifact_links: list[Any]) -> str:
    recipe = _mapping(detail.get("edit_recipe"))
    scale = _mapping(recipe.get("scale"))
    targets = _mapping(recipe.get("targets_mm"))
    intent = _mapping(recipe.get("geometry_intent"))
    geometry = _mapping(detail.get("geometry"))
    return "\n".join(
        [
            f'        <form class="controls" action="/runs/{quote(run_id, safe="")}/edits" method="post">',
            "          <h2>Edit Geometry</h2>",
            '          <div class="controls-body">',
            f'            <p class="issue-line">{escape(_fit_issue_label(detail))}</p>',
            '            <p class="muted">Tune opening width, arch clearance, sole texture, TPU-safe supports, and external spool assumptions before slicing again.</p>',
            '            <section class="input-card">',
            "              <h3>Input prompt / mesh summary</h3>",
            f"              <p>{escape(_detail_input_summary(detail))}</p>",
            f"              <p>Current geometry: {escape(_format_bounds(geometry.get('bounds_mm')))}</p>",
            f"              <p>Current issue: {escape(_fit_issue_label(detail))}</p>",
            "            </section>",
            '            <div class="control-grid">',
            _number_field("Overall scale", "overall_scale", _field_value(scale, "overall", "1.0"), suffix="x"),
            _number_field("X scale", "x_scale", _field_value(scale, "x", "1.0"), suffix="x"),
            _number_field("Y scale", "y_scale", _field_value(scale, "y", "1.0"), suffix="x"),
            _number_field("Z scale", "z_scale", _field_value(scale, "z", "1.0"), suffix="x"),
            _number_field("Target length", "target_length_mm", _field_value(targets, "length", ""), suffix="mm"),
            _number_field("Target width", "target_width_mm", _field_value(targets, "width", ""), suffix="mm"),
            _number_field("Target height", "target_height_mm", _field_value(targets, "height", ""), suffix="mm"),
            _number_field("Widen / narrow opening", "opening_delta_mm", _field_value(intent, "opening_width_delta_mm", "0"), suffix="mm"),
            _number_field("Raise / lower arch/opening", "arch_delta_mm", _field_value(intent, "arch_height_delta_mm", "0"), suffix="mm"),
            _number_field("Wall thickness", "wall_thickness_mm", _field_value(intent, "wall_thickness_mm", "2.4"), suffix="mm"),
            "            </div>",
            f'            <label class="check-row"><input type="checkbox" name="flat_base"{_checked(intent.get("flat_base", True))}> Flat base</label>',
            "            <label><span>Support strategy</span><select name=\"support_strategy\">",
            _support_option(recipe, "auto", "Auto from support risk"),
            _support_option(recipe, "snug_tree_auto", "TPU-safe snug/tree supports + external spool review"),
            _support_option(recipe, "tree", "Tree supports"),
            _support_option(recipe, "minimal", "Minimal supports"),
            _support_option(recipe, "none", "No supports"),
            "            </select></label>",
            "            <label><span>Freeform edit instruction</span>",
            (
                '              <textarea name="edit_instruction" rows="4" '
                'placeholder="Example: widen the front opening by 8 mm and keep the arch lower.">'
                f'{escape(str(recipe.get("instruction", "")))}'
                "</textarea>"
            ),
            "            </label>",
            '            <div class="edit-actions"><button class="primary" type="submit">Rebuild from edits</button></div>',
            (
                '            <p class="recipe-preview">Recipe preview: '
                f"opening {_signed_mm(intent.get('opening_width_delta_mm', 0))}, "
                f"arch {_signed_mm(intent.get('arch_height_delta_mm', 0))}, "
                f"Y scale {escape(_field_value(scale, 'y', '1.0'))}.</p>"
            ),
            '            <p class="muted">Creates a non-destructive edit run; original artifacts stay untouched.</p>',
            "            <section><h3>Artifact Links</h3>",
            _render_artifact_tiles(artifact_links),
            "            </section>",
            "          </div>",
            "        </form>",
        ]
    )


def _render_stage_panel(title: str, stages: list[dict[str, Any]]) -> str:
    rows = "\n".join(_render_stage_row(stage) for stage in stages) or '<p class="muted">No stage data yet.</p>'
    return "\n".join(
        [
            '            <article class="card stage-card">',
            f"              <h2>{escape(title)}</h2>",
            f'              <div class="card-body stage-rail">{rows}</div>',
            "            </article>",
        ]
    )


def _render_stage_row(stage: dict[str, Any]) -> str:
    label = str(stage.get("label", "Pipeline step"))
    state = str(stage.get("state") or stage.get("status") or "unknown")
    detail = str(stage.get("detail") or stage.get("message") or "Not run yet.")
    tone = _state_tone(state)
    return "\n".join(
        [
            '                <div class="stage">',
            f'                  <span class="node node-{escape(tone, quote=True)}"></span>',
            f"                  <div><h3>{escape(label)}</h3><p>{escape(detail)}</p></div>",
            f'                  <span class="badge badge-{escape(tone, quote=True)}">{escape(_state_label(state))}</span>',
            "                </div>",
        ]
    )


def _render_warning_receipts(detail: dict[str, Any]) -> str:
    warnings = [str(warning) for warning in _as_list(detail.get("warnings")) if str(warning)]
    failed = [stage for stage in _as_dicts(detail.get("pipeline")) if _state_tone(str(stage.get("status", "unknown"))) == "fail"]
    if not warnings and not failed:
        return ""
    warning_rows = "".join(f"<li>{escape(warning)}</li>" for warning in warnings[:4]) or "<li>No warnings recorded.</li>"
    failed_rows = "".join(
        f"<li><strong>{escape(str(stage.get('label', 'Stage')))}</strong>: {escape(str(stage.get('message', 'Failed.')))}</li>"
        for stage in failed[:4]
    ) or "<li>No failed pipeline stages.</li>"
    return "\n".join(
        [
            '          <article class="card warning-receipts">',
            "            <h2>Warning and Failure Receipts</h2>",
            '            <div class="receipt-grid">',
            f"              <section><h3>Warnings</h3><ul>{warning_rows}</ul></section>",
            f"              <section><h3>Failed stages</h3><ul>{failed_rows}</ul></section>",
            "            </div>",
            "          </article>",
        ]
    )


def _render_metric(label: str, value: str) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _render_open_folder_actions(run_id: str) -> str:
    safe_run_id = quote(run_id, safe="")
    return "\n".join(
        [
            '            <div class="open-folder-actions">',
            f'              <form method="post" action="/runs/{safe_run_id}/open-folder/bundle"><button type="submit">Open bundle folder</button></form>',
            f'              <form method="post" action="/runs/{safe_run_id}/open-folder/report"><button type="submit">Open report folder</button></form>',
            "            </div>",
        ]
    )


def _number_field(label: str, name: str, value: str, *, suffix: str) -> str:
    return (
        "<label>"
        f"<span>{escape(label)} ({escape(suffix)})</span>"
        f'<input type="number" name="{escape(name, quote=True)}" value="{escape(value, quote=True)}" step="0.1">'
        "</label>"
    )


def _render_artifact_tiles(artifact_links: list[Any]) -> str:
    items = "".join(_render_primary_artifact_tile(label, categories, artifact_links) for label, categories in _PRIMARY_ARTIFACT_TILES)
    return f'<div class="links">{items}</div>'


_PRIMARY_ARTIFACT_TILES = (
    ("Original mesh", ("generated_mesh", "original_input")),
    ("Repaired mesh", ("repaired_mesh",)),
    ("Final STL", ("oriented_mesh",)),
    ("3MF", ("bundle",)),
    ("Slice report", ("slice_log",)),
)


def _render_primary_artifact_tile(label: str, categories: tuple[str, ...], artifact_links: list[Any]) -> str:
    link = _first_artifact_link(categories, artifact_links)
    if link is None:
        return f'<span class="missing-artifact"><strong>{escape(label)}</strong><span>Pending</span></span>'
    path = str(getattr(link, "path", getattr(link, "download_name", "")))
    download_attribute = _download_attribute(link)
    return (
        f'<a href="{escape(str(getattr(link, "href", "#")), quote=True)}"{download_attribute}>'
        f"<strong>{escape(label)}</strong><span>{escape(path)}</span></a>"
    )


def _download_attribute(link: Any) -> str:
    category = str(getattr(link, "category", ""))
    download_name = str(getattr(link, "download_name", ""))
    media_type = str(getattr(link, "media_type", ""))
    if category == "bundle" and download_name.lower().endswith(".3mf") and media_type == "model/3mf":
        return f' download="{escape(download_name, quote=True)}"'
    return ""


def _first_artifact_link(categories: tuple[str, ...], artifact_links: list[Any]) -> Any | None:
    for category in categories:
        for link in artifact_links:
            if str(getattr(link, "category", "")) == category:
                return link
    return None


def _key_value_strip(class_name: str, aria_label: str, items: list[tuple[str, str]]) -> str:
    rendered = "".join(
        f'<div class="context-item"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in items
    )
    return f'<section class="{escape(class_name, quote=True)}" aria-label="{escape(aria_label, quote=True)}">{rendered}</section>'


def _render_provider_items(items: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="provider-item"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in items
    )


def _validation_by_key(detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for check in _as_list(detail.get("validation")):
        if isinstance(check, dict):
            checks[str(check.get("key") or _class_name(str(check.get("label", ""))))] = check
    return checks


def _state_tone(state: str) -> str:
    normalized = _class_name(state)
    if normalized in {"pass", "passed", "ready", "succeeded", "success"}:
        return "pass"
    if normalized in {"fail", "failed", "blocked", "error"}:
        return "fail"
    return "warn"


def _state_label(state: str) -> str:
    tone = _state_tone(state)
    return "Pass" if tone == "pass" else "Fail" if tone == "fail" else "Review"


def _format_bounds(value: Any) -> str:
    if not isinstance(value, list | tuple) or not value:
        return "Bounds pending"
    parts: list[str] = []
    for item in value[:3]:
        try:
            parts.append(f"{float(item):g}")
        except (TypeError, ValueError):
            continue
    return " x ".join(parts) + " mm" if parts else "Bounds pending"


def _format_metric(value: Any, suffix: str) -> str:
    if value in {None, ""}:
        return "pending"
    try:
        return f"{float(value):g} {suffix}"
    except (TypeError, ValueError):
        return str(value)


def _artifact_primary_label(artifact_links: list[Any]) -> str:
    for category in ("oriented_mesh", "repaired_mesh", "generated_mesh", "preview", "bundle", "reports"):
        for link in artifact_links:
            if str(getattr(link, "category", "")) == category:
                return str(getattr(link, "label", "Artifact"))
    return "preview artifact pending"


def _primary_model_preview(preview_links: list[Any]) -> Any | None:
    for link in preview_links:
        text = f"{getattr(link, 'label', '')} {getattr(link, 'path', '')}".lower()
        if "run detail" in text or "model_preview" in text or "model preview" in text:
            return link
    return None


def _fit_issue_label(detail: dict[str, Any]) -> str:
    warnings = [str(warning).lower() for warning in _as_list(detail.get("warnings"))]
    if any("narrow" in warning or "opening" in warning for warning in warnings):
        return "Needs geometry edit: upper/opening too narrow"
    failed_stage = _first_failed_pipeline_stage(detail)
    if failed_stage:
        return f"Pipeline failed: {failed_stage}"
    checks = _validation_by_key(detail)
    bed_fit = checks.get("bed_fit")
    if bed_fit and _state_tone(str(bed_fit.get("state", "review"))) != "pass":
        return "Bed fit needs review"
    support = checks.get("support_risk")
    if support and _state_tone(str(support.get("state", "review"))) != "pass":
        return "Support strategy needs review"
    slice_success = checks.get("slice_success")
    if slice_success and _state_tone(str(slice_success.get("state", "review"))) != "pass":
        return "Slice gate not verified"
    return "None flagged"


def _verdict_heading(detail: dict[str, Any]) -> str:
    tone = _state_tone(str(_mapping(detail.get("print_verdict")).get("state", "review")))
    issue = _fit_issue_label(detail)
    if (
        _is_slipper_context(detail)
        and issue == "Needs geometry edit: upper/opening too narrow"
        and tone != "pass"
    ):
        return "Not yet: rebuild required"
    if tone == "pass":
        return "Ready to inspect in Bambu Studio"
    return str(_mapping(detail.get("print_verdict")).get("label") or "Review before print")


def _verdict_reason(detail: dict[str, Any]) -> str:
    issue = _fit_issue_label(detail)
    if _is_slipper_context(detail) and issue == "Needs geometry edit: upper/opening too narrow":
        return (
            "Repair and bed-fit checks can pass while the wearable TPU geometry still needs review; "
            "fix the upper/opening, support policy, and slice handoff before trusting this run."
        )
    if _is_slipper_context(detail) and issue == "Slice gate not verified":
        return (
            "Repair, bed fit, and bundle validation have receipts, but this run still needs "
            "Bambu Studio layer-preview or slice verification before printing."
        )
    if _is_slipper_context(detail) and issue == "Support strategy needs review":
        return (
            "Support settings may be recorded in the bundle, but support risk still needs "
            "Bambu Studio layer-preview review before printing."
        )
    if _is_slipper_context(detail) and issue == "Bed fit needs review":
        return "Bed fit still needs review before this run can be trusted."
    return str(_mapping(detail.get("print_verdict")).get("reason") or "Print readiness pending.")


def _is_slipper_context(detail: dict[str, Any]) -> bool:
    parts = [
        str(detail.get("run_id", "")),
        _detail_input_summary(detail),
        _edit_delta_summary(detail),
        " ".join(str(warning) for warning in _as_list(detail.get("warnings"))),
    ]
    blob = " ".join(parts).lower()
    return any(term in blob for term in ("slipper", "upper", "opening", "sole"))


def _next_action_label(detail: dict[str, Any]) -> str:
    state = str(_mapping(detail.get("print_verdict")).get("state", "review"))
    failed_stage = _first_failed_pipeline_stage(detail)
    if failed_stage:
        return f"Fix the failed {failed_stage} stage, then rebuild this run."
    if _state_tone(state) == "fail":
        return "Fix the failed validation check, then rebuild this run."
    warnings = [str(warning).lower() for warning in _as_list(detail.get("warnings"))]
    if any("narrow" in warning or "opening" in warning for warning in warnings):
        return "Widen the upper/opening and rebuild from edits."
    support = _validation_by_key(detail).get("support_risk", {})
    if _state_tone(str(support.get("state", "review"))) == "warn":
        return "Choose a support strategy, then rebuild or inspect the slice receipt."
    slice_success = _validation_by_key(detail).get("slice_success", {})
    if _state_tone(str(slice_success.get("state", "review"))) != "pass":
        return "Open the 3MF in Bambu Studio and inspect the slice preview before printing."
    if _state_tone(state) == "pass":
        return "Open the 3MF and inspect the slice receipt before printing."
    return "Inspect warnings, then either rebuild or open the current bundle."


def _edit_delta_summary(detail: dict[str, Any]) -> str:
    recipe = _mapping(detail.get("edit_recipe"))
    scale = _mapping(recipe.get("scale"))
    intent = _mapping(recipe.get("geometry_intent"))
    deltas = []
    y_scale = _field_value(scale, "y", "1.0")
    if y_scale not in {"", "1", "1.0", "1.00"}:
        deltas.append(f"Y scale {y_scale}")
    for label, key in (("opening", "opening_width_delta_mm"), ("arch", "arch_height_delta_mm")):
        value = intent.get(key)
        if value not in {None, "", 0, 0.0}:
            deltas.append(f"{label} {_signed_mm(value)}")
    support = str(recipe.get("support_strategy", "auto"))
    if support and support != "auto":
        deltas.append(f"support {support}")
    return ", ".join(deltas) if deltas else "No geometry delta recorded"


def _first_warning(detail: dict[str, Any]) -> str:
    warnings = [str(warning) for warning in _as_list(detail.get("warnings")) if str(warning)]
    if not warnings:
        return "None"
    first = warnings[0]
    return first if len(first) <= 96 else f"{first[:93]}..."


def _first_failed_pipeline_stage(detail: dict[str, Any]) -> str:
    for stage in _as_dicts(detail.get("pipeline")):
        if _state_tone(str(stage.get("status", "unknown"))) == "fail":
            return str(stage.get("label") or "pipeline")
    return ""


def _label_from_detail(detail: dict[str, Any], key: str, fallback: str) -> str:
    label = str(_mapping(detail.get(key)).get("label") or "").strip()
    if label:
        return label
    settings = _mapping(detail.get("settings"))
    for suffix in ("label", "id", "name"):
        value = settings.get(f"{key}_{suffix}")
        if value:
            return str(value)
    return fallback


def _use_case_label(detail: dict[str, Any]) -> str:
    settings = _mapping(detail.get("settings"))
    launch_options = _mapping(detail.get("launch_options"))
    for payload in (settings, launch_options):
        value = payload.get("use_case")
        if value:
            return str(value)
    return "not recorded"


def _flex_coupon_status(detail: dict[str, Any], artifact_links: list[Any]) -> str:
    required = _requires_flex_coupon(detail)
    present = _has_flex_coupon_artifact(artifact_links)
    evidence = _mapping(detail.get("physical_evidence"))
    if required and _physical_packet_is_credible(evidence):
        return "Required; physical coupon evidence recorded"
    if required and present:
        return "Required; coupon artifact generated, physical print not recorded"
    if required:
        return "Required; no coupon artifact found"
    if present:
        return "Coupon artifact present; requirement not inferred"
    return "Not required by recorded material/profile"


def _physical_gate_status(detail: dict[str, Any]) -> str:
    evidence = _mapping(detail.get("physical_evidence"))
    if not evidence.get("available"):
        return "Physical coupon/print evidence not recorded"
    if _physical_packet_is_credible(evidence):
        return f"Physical evidence recorded: {str(evidence.get('print_status', 'recorded'))}"
    missing = [str(item) for item in _as_list(evidence.get("missing_required_evidence"))]
    if missing:
        return "Physical evidence incomplete: " + ", ".join(missing)
    return "Physical evidence recorded; review packet"


def _physical_packet_is_credible(evidence: dict[str, Any]) -> bool:
    if not evidence.get("available"):
        return False
    if _as_list(evidence.get("missing_required_evidence")):
        return False
    return str(evidence.get("print_status", "")).lower() in {"passed", "failed", "partial"}


def _physical_evidence_heading(evidence: dict[str, Any]) -> str:
    status = str(evidence.get("print_status") or "recorded").strip().lower()
    print_type = str(evidence.get("print_type") or "print").strip().lower()
    object_label = str(evidence.get("object_label") or "object").strip()
    if status in {"passed", "failed", "partial"}:
        return f"{status.title()} physical {print_type}: {object_label}"
    return f"Physical {print_type} recorded: {object_label}"


def _physical_link(run_id: str, label: str, path: Any) -> str:
    if not path:
        return ""
    path_text = str(path)
    href = f"/runs/{quote(run_id, safe='')}/artifacts/{quote(path_text, safe='/.')}"
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def _prompt_provider_heading(prompt_reference: dict[str, Any]) -> str:
    provider = _prompt_provider_label(prompt_reference.get("provider"))
    status = _state_label(str(prompt_reference.get("stage_status", "review")))
    return f"{provider} reference generation: {status}"


def _prompt_provider_label(value: Any) -> str:
    provider = str(value or "unknown").strip().lower()
    if provider == "openai":
        return "OpenAI"
    if provider == "command":
        return "Command"
    return provider.title() if provider else "Unknown"


def _privacy_mode_label(value: Any) -> str:
    mode = str(value or "not recorded").strip().lower()
    if mode == "remote_api":
        return "remote API"
    if mode == "local_or_user_configured":
        return "local or user-configured"
    return mode.replace("_", " ")


def _prompt_budget_status_label(prompt_reference: dict[str, Any]) -> str:
    status = str(prompt_reference.get("budget_status") or "review")
    labels = {
        "blocked": "Budget blocked before remote work",
        "within_cap": "Within configured cap",
        "within_cap_pending": "Within cap; provider did not finish",
        "unchecked": "Cap set; estimate missing",
        "not_capped": "No max cost cap recorded",
    }
    return labels.get(status, "Review budget receipt")


def _remote_prompt_note(prompt_reference: dict[str, Any]) -> str:
    remote_upload = prompt_reference.get("remote_upload")
    stores_prompt = prompt_reference.get("stores_prompt_with_provider")
    if remote_upload is True:
        storage = "prompt may be stored by provider" if stores_prompt is True else "storage policy not recorded"
        return f"Remote prompt/reference request; {storage}."
    if remote_upload is False:
        return "No remote upload recorded for this provider."
    return "Remote upload behavior depends on the configured provider command."


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


def _requires_flex_coupon(detail: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            _label_from_detail(detail, "material", ""),
            _label_from_detail(detail, "profile", ""),
            _use_case_label(detail),
            " ".join(str(warning) for warning in _as_list(detail.get("warnings"))),
        ]
    ).lower()
    return any(token in haystack for token in ("tpu", "flex", "slipper", "wearable"))


def _has_flex_coupon_artifact(artifact_links: list[Any]) -> bool:
    for link in artifact_links:
        text = " ".join(
            str(getattr(link, attr, ""))
            for attr in ("category", "label", "path", "download_name")
        ).lower()
        if "calibration_mesh" in text or "flex_coupon" in text or "flex coupon" in text:
            return True
    return False


def _signed_mm(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    sign = "+" if number >= 0 else ""
    return f"{sign}{number:g} mm"


def _support_option(recipe: dict[str, Any], value: str, label: str) -> str:
    selected = " selected" if str(recipe.get("support_strategy", "auto")) == value else ""
    return f'<option value="{escape(value, quote=True)}"{selected}>{escape(label)}</option>'


def _detail_input_summary(detail: dict[str, Any]) -> str:
    return " · ".join(
        [
            f"Input: {_mapping(detail.get('input')).get('kind', 'unknown')}",
            str(_mapping(detail.get("printer")).get("label") or "Printer not selected"),
            str(_mapping(detail.get("material")).get("label") or "Material not selected"),
            str(_mapping(detail.get("profile")).get("label") or "Profile pending"),
        ]
    )


def _field_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    return default if value is None else str(value)


def _checked(value: Any) -> str:
    return " checked" if bool(value) else ""


def _class_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character == "-" else "-" for character in value.lower())
    return cleaned.strip("-") or "unknown"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _as_list(value) if isinstance(item, dict)]


RUN_DETAIL_CSS = """
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.45; color: #17202a; background: #f6f8fb; }
    body { margin: 0; }
    .run-detail-app { background: radial-gradient(circle at 10% 0%, rgba(50,125,158,.12), transparent 28rem), linear-gradient(135deg,#f6f8fb 0%,#eef2f5 58%,#e7edf2 100%); min-height: 100vh; padding: 0 0 40px; }
    .topbar { align-items: center; backdrop-filter: blur(16px); background: rgba(249,250,251,.9); border-bottom: 1px solid #cfd8e3; display: grid; gap: 20px; grid-template-columns: minmax(0,1fr) auto; margin: 0; padding: 18px clamp(18px,3vw,36px); position: sticky; top: 0; z-index: 5; }
    .topbar h1 { font-size: clamp(1.5rem,2.3vw,2.35rem); margin: 0 0 6px; word-break: break-word; }
    .eyebrow,.score span,.metric span,.context-item span { color: #607080; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .72rem; font-weight: 850; text-transform: uppercase; }
    .run-meta { color: #52606d; display: flex; flex-wrap: wrap; gap: 8px; font-size: .86rem; }
    .run-meta span { background: #fff; border: 1px solid #d9e2ec; border-radius: 999px; padding: 4px 8px; }
    .status-chip { align-self: center; border: 1px solid #b8c6d4; border-radius: 999px; font-weight: 850; padding: 9px 12px; white-space: nowrap; }
    .status-chip-pass { background: #e3f8ec; border-color: #a6d8ba; color: #126237; } .status-chip-warn { background: #fff4d6; border-color: #e7c36d; color: #7c4a03; } .status-chip-fail { background: #fde8e8; border-color: #e6a6a6; color: #9b1c1c; }
    .shell { display: grid; gap: 16px; margin: 0 auto; max-width: 1620px; padding: clamp(14px,2vw,24px); }
    .verdict-strip { border-top: 4px solid transparent; display: grid; gap: 10px; grid-template-columns: 1.2fr repeat(5,minmax(110px,1fr)); }
    .verdict-strip-pass { border-color: #1f8a4c; } .verdict-strip-warn { border-color: #b7791f; } .verdict-strip-fail { border-color: #c23030; }
    .verdict,.score,.model-card,.card,.controls,.run-context,.prompt-provider,.physical-evidence { background: rgba(255,255,255,.94); border: 1px solid #cfd8e3; border-radius: 8px; box-shadow: 0 18px 46px rgba(36,47,61,.1); }
    .verdict { background: #17202a; color: #f8fafc; padding: 14px; } .verdict h2 { font-size: clamp(1.35rem,2.1vw,2rem); margin: 0 0 6px; } .verdict p { color: #d8e2ec; }
    .verdict-issue { color:#fff; display:block; font-size:.98rem; margin: 0 0 8px; overflow-wrap:anywhere; }
    .next-action { background: rgba(255,255,255,.08); border: 1px solid rgba(216,226,236,.22); border-radius: 8px; margin: 12px 0 0; padding: 9px 10px; }
    .next-action span { color:#9fb3c8; display:block; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.68rem; font-weight:850; letter-spacing:.02em; text-transform:uppercase; }
    .score { display:grid; min-height:118px; padding: 14px; } .score p { align-self:end; color:#52606d; font-size:.78rem; margin:8px 0 0; overflow-wrap:anywhere; }
    .score strong,.metric strong { display: block; font-size: 1.18rem; margin-top: 6px; overflow-wrap: anywhere; }
    .score-pass strong { color: #126237; } .score-warn strong { color: #7c4a03; } .score-fail strong { color: #9b1c1c; }
    .run-context,.print-context { display: grid; gap: 1px; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); overflow: hidden; } .print-context { border-left: 4px solid #327d9e; } .context-item { background: #fff; min-width: 0; padding: 11px 12px; } .context-item strong { display: block; overflow-wrap: anywhere; }
    .prompt-provider { align-items:center; border-left:4px solid #7c4a03; display:grid; gap:14px; grid-template-columns:minmax(0,1fr) minmax(300px,.72fr); padding:14px; } .prompt-provider h2{font-size:1.1rem;margin:0 0 4px}.prompt-provider p{color:#52606d;margin:4px 0}.provider-note{font-weight:800}.provider-grid{display:grid;gap:1px;grid-template-columns:repeat(2,minmax(0,1fr));overflow:hidden}.provider-item{background:#f8fafc;border:1px solid #e4e7eb;margin:-1px 0 0 -1px;min-width:0;padding:9px}.provider-item span{color:#607080;display:block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.68rem;font-weight:850;text-transform:uppercase}.provider-item strong{display:block;overflow-wrap:anywhere}
    .physical-evidence { align-items:center; display:grid; gap:14px; grid-template-columns:minmax(0,1fr) auto; padding:14px; } .physical-evidence h2{font-size:1.1rem;margin:0 0 4px}.physical-evidence p{color:#52606d;margin:4px 0}.evidence-missing{font-weight:800}.evidence-links{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}.evidence-links a{background:#eef6f9;border:1px solid #c6dfe9;border-radius:999px;color:#24566d;font-size:.84rem;font-weight:800;padding:7px 10px;text-decoration:none}
    .workbench { display: grid; gap: clamp(14px,2vw,24px); grid-template-columns: minmax(0,1fr) minmax(330px,410px); }
    .canvas-zone { display: grid; gap: 14px; grid-template-rows: minmax(420px,auto) auto auto; min-width: 0; }
    .model-card { display: grid; grid-template-rows: auto minmax(420px,1fr) auto auto; min-height: 520px; overflow: hidden; }
    .toolbar { align-items: center; border-bottom: 1px solid #cfd8e3; display: flex; gap: 10px; justify-content: space-between; padding: 12px 14px; }
    .view-tabs { display: flex; flex-wrap: wrap; gap: 6px; } .tab { background: #f8fafc; border: 1px solid #cfd8e3; border-radius: 999px; color: #52606d; font-size: .84rem; font-weight: 750; padding: 7px 10px; } .tab.active { background: #17202a; color: #fff; }
    .model-view { align-items: center; background: linear-gradient(90deg,rgba(50,125,158,.12) 1px,transparent 1px),linear-gradient(rgba(50,125,158,.1) 1px,transparent 1px),radial-gradient(circle at 50% 44%,rgba(50,125,158,.13),transparent 34%),#f7fafc; background-size:42px 42px,42px 42px,auto,auto; display:grid; justify-items:center; margin:0; overflow:hidden; position:relative; }
    .bed { background: rgba(255,255,255,.3); border: 2px solid rgba(50,125,158,.42); border-radius: 8px; bottom: 8%; height: min(48%,430px); position: absolute; transform: perspective(920px) rotateX(62deg); width: min(82%,860px); }
    .mesh-placeholder { aspect-ratio: 2.1; background: linear-gradient(90deg,rgba(255,255,255,.72) 0 1px,transparent 1px 22px),linear-gradient(rgba(255,255,255,.65) 0 1px,transparent 1px 22px),linear-gradient(135deg,rgba(50,125,158,.26),rgba(255,255,255,.54)); border: 3px solid rgba(23,32,42,.68); border-radius: 14px; width: min(54vw,650px); z-index: 1; }
    .model-preview-image { display:block; max-height:80%; max-width:88%; object-fit:contain; position:relative; width:min(60vw,760px); z-index:1; }
    .risk-marker,.measure,.preview-title { background: rgba(255,255,255,.9); border: 1px dashed rgba(23,32,42,.5); font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size: .78rem; padding: 4px 7px; position: absolute; z-index: 2; }
    .risk-marker { border: 2px solid #c23030; color:#9b1c1c; font-weight:900; right:18%; top:43%; } .measure-x { bottom:15%; left:19%; } .measure-z { right:13%; top:25%; }
    .model-footer { background:#cfd8e3; border-top:1px solid #cfd8e3; display:grid; gap:1px; grid-template-columns:repeat(4,minmax(0,1fr)); } .metric { background:#fff; min-width:0; padding:12px; }
    .workbench-artifacts { border-top:1px solid #cfd8e3; display:grid; gap:10px; padding:12px 14px 14px; } .artifact-heading { align-items:baseline; display:flex; flex-wrap:wrap; gap:8px 12px; justify-content:space-between; } .artifact-heading h3{margin:0}
    .lower-grid { display:grid; gap:14px; grid-template-columns:1fr 1fr; } .card h2,.controls h2 { border-bottom:1px solid #cfd8e3; font-size:1rem; margin:0; padding:13px 14px; } .card-body,.controls-body { display:grid; gap:13px; padding:14px; }
    .stage { align-items:start; border-bottom:1px solid #e4e7eb; display:grid; gap:10px; grid-template-columns:18px minmax(0,1fr) auto; padding:9px 0; } .stage:last-child{border-bottom:0} .stage h3{font-size:.92rem;margin:0 0 2px}.stage p{color:#52606d;font-size:.84rem;margin:0}
    .node { background:#b8c6d4; border-radius:50%; height:14px; margin-top:3px; width:14px; } .node-pass{background:#1f8a4c}.node-warn{background:#b7791f}.node-fail{background:#c23030}
    .badge { align-self:start; border-radius:999px; font-size:.7rem; font-weight:900; padding:4px 8px; text-transform:uppercase; } .badge-pass{background:#e3f8ec;color:#126237}.badge-warn{background:#fff4d6;color:#7c4a03}.badge-fail{background:#fde8e8;color:#9b1c1c}
    .warning-receipts { padding: 0; } .receipt-grid { display:grid; gap:12px; grid-template-columns:1fr 1fr; padding:14px; } .receipt-grid h3{margin:0 0 8px}.receipt-grid ul{margin:0;padding-left:18px}
    input,select,textarea,button{box-sizing:border-box;font:inherit;width:100%} input,select,textarea{border:1px solid #bcccdc;border-radius:6px;padding:8px 10px} button{background:#0b5cad;border:0;border-radius:6px;color:#fff;cursor:pointer;font-weight:700;min-height:40px;padding:8px 14px}
    .controls { align-self:start; margin:0; overflow:hidden; } .control-grid{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}.issue-line{background:#eef6f9;border:1px solid #c6dfe9;border-radius:8px;color:#24566d;font-weight:850;margin:0;padding:10px}.input-card{border-left:5px solid #327d9e;padding-left:12px}.input-card p,.muted{color:#52606d}.check-row{align-items:center;background:#f8fafc;border:1px solid #cfd8e3;border-radius:8px;color:#17202a;display:flex;gap:8px;justify-content:space-between;padding:10px;text-transform:none}.check-row input{min-height:auto;width:auto}.primary{background:#327d9e;max-width:none}.edit-actions{background:linear-gradient(rgba(255,255,255,.86),#fff);bottom:0;padding-top:8px;position:sticky;z-index:2}.recipe-preview{background:#eef6f9;border:1px solid #c6dfe9;border-radius:8px;color:#24566d;margin:0;padding:10px}
    .links{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr))}.workbench-artifacts .links{grid-template-columns:repeat(5,minmax(0,1fr))}.links a,.missing-artifact{background:#f8fafc;border:1px solid #cfd8e3;border-radius:8px;display:block;font-weight:850;padding:10px}.links span{color:#52606d;display:block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem;margin-top:4px;overflow-wrap:anywhere}.open-folder-actions{display:grid;gap:8px;grid-template-columns:repeat(2,minmax(0,1fr))}
    @media (max-width:1180px){.verdict-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.verdict{grid-column:1/-1}.workbench{grid-template-columns:1fr}.controls{order:-1}}
    @media (max-width:760px){.topbar,.verdict-strip,.lower-grid,.model-footer,.workbench-artifacts .links,.control-grid,.receipt-grid,.open-folder-actions,.prompt-provider,.provider-grid,.physical-evidence{grid-template-columns:1fr}.status-chip{white-space:normal}.model-card{min-height:430px}.mesh-placeholder,.model-preview-image{width:86vw}.evidence-links{justify-content:flex-start}}
""".strip()


__all__ = ["RUN_DETAIL_CSS", "render_run_detail_page"]
