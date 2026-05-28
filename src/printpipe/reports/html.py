"""Dependency-free HTML report rendering for PrintPipe runs."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from printpipe.contracts import Artifact, ArtifactKind
from printpipe.runs.paths import RunLayout


def render_html_report(
    report_dict: Mapping[str, Any],
    *,
    layout: RunLayout | None = None,
) -> str:
    """Render a local HTML run report from the structured report dictionary."""

    run_id = _as_text(report_dict.get("run_id", "unknown-run"))
    stages = _as_list(report_dict.get("stages"))
    artifacts = _as_list(report_dict.get("artifacts"))
    warnings = _as_list(report_dict.get("warnings"))
    settings_changes = _as_list(report_dict.get("settings_changes"))
    pre_print_checklist = _as_list(report_dict.get("pre_print_checklist"))

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>PrintPipe Run Report: {run_id}</title>",
            f"  <style>{_CSS}</style>",
            "</head>",
            "<body>",
            "  <main>",
            "    <header>",
            "      <p>PrintPipe run report</p>",
            f"      <h1>{run_id}</h1>",
            "    </header>",
            _render_input_section(stages, artifacts, layout=layout),
            _render_prompt_reference_section(stages),
            _render_previews_section(stages, artifacts, layout=layout),
            _render_mesh_repair_section(stages, artifacts, layout=layout),
            _render_bed_fit_section(stages, artifacts, layout=layout),
            _render_slice_summary(stages, artifacts, layout=layout),
            _render_warnings_section(warnings),
            _render_settings_changes_section(settings_changes),
            _render_pre_print_checklist_section(pre_print_checklist),
            _render_stages(stages, layout=layout),
            _render_artifacts(artifacts, layout=layout),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def write_html_report(layout: RunLayout, report_dict: Mapping[str, Any]) -> Artifact:
    """Write run_report.html into the run reports directory and return its artifact."""

    layout.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = layout.reports_dir / "run_report.html"
    report_path.write_text(render_html_report(report_dict, layout=layout), encoding="utf-8")
    return Artifact(
        kind=ArtifactKind.REPORT,
        path=report_path,
        label="Run report HTML",
    )


def _render_input_section(
    stages: list[Any],
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
) -> str:
    input_artifacts = _artifacts_with_kinds(
        artifacts,
        {"original_input", "cleaned_frame"},
    )
    input_stages = _stages_matching(stages, ("input", "frame"))
    body = "\n".join(
        [
            _render_artifact_cards(
                input_artifacts,
                layout=layout,
                empty="No input artifact recorded yet.",
            ),
            _render_stage_cards(input_stages),
        ]
    )
    return _section("Input", body, classes=("section-input",))


def _render_previews_section(
    stages: list[Any],
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
) -> str:
    preview_artifacts = _unique_artifacts(
        [
            *[
                artifact
                for artifact in artifacts
                if _artifact_kind(artifact) == "preview"
            ],
            *_preview_artifacts_from_stages(stages),
        ]
    )
    return _section(
        "Previews",
        _render_artifact_cards(
            preview_artifacts,
            layout=layout,
            empty="No preview artifacts recorded yet.",
        ),
        classes=("section-previews",),
    )


def _render_prompt_reference_section(stages: list[Any]) -> str:
    stage = _first_prompt_reference_stage(stages)
    if stage is None:
        return ""
    metrics = stage.get("metrics", {})
    metrics = metrics if isinstance(metrics, Mapping) else {}
    quote = metrics.get("provider_quote", {})
    quote = quote if isinstance(quote, Mapping) else {}
    provider = quote.get("provider") or metrics.get("provider") or "unknown"
    status = str(stage.get("status", "unknown"))
    status_class = _class_name(status)
    items = [
        ("Provider", _prompt_provider_label(provider)),
        ("Status", status),
        ("Privacy", _privacy_mode_label(quote.get("privacy_mode"))),
        ("Estimated cost", _format_money(quote.get("estimated_cost_usd"))),
        ("Max cost", _format_money(quote.get("max_cost_usd"))),
        ("Latency", _format_seconds(quote.get("estimated_seconds"))),
        ("Budget", _prompt_budget_label(stage, quote)),
    ]
    body = "\n".join(
        [
            '<div class="prompt-reference-summary">',
            "      <div>",
            f"        <h3>{_prompt_provider_label(provider)} prompt reference</h3>",
            f'        <span class="status status-{status_class}">{_as_text(status)}</span>',
            f"        <p>{_as_text(stage.get('message', 'No provider message recorded.'))}</p>",
            f'        <p class="provider-note">{_as_text(_remote_prompt_note(quote))}</p>',
            "      </div>",
            f'      <dl class="prompt-reference-grid">{_render_prompt_reference_items(items)}</dl>',
            "    </div>",
        ]
    )
    return _section("Prompt Reference", body, classes=("section-prompt-reference",))


def _render_mesh_repair_section(
    stages: list[Any],
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
) -> str:
    mesh_artifacts = _artifacts_with_kinds(
        artifacts,
        {"generated_mesh", "repaired_mesh", "oriented_mesh"},
    )
    mesh_stages = _stages_matching(stages, ("mesh", "repair"))
    body = "\n".join(
        [
            _render_artifact_cards(
                mesh_artifacts,
                layout=layout,
                empty="No mesh artifacts recorded yet.",
            ),
            _render_stage_cards(mesh_stages),
        ]
    )
    return _section("Mesh and Repair", body, classes=("section-mesh-repair",))


def _render_bed_fit_section(
    stages: list[Any],
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
) -> str:
    bed_stages = _stages_matching(stages, ("bed", "orient", "geometry", "min_margin"))
    bed_artifacts = _unique_artifacts(
        [
            *[
                artifact
                for artifact in artifacts
                if _artifact_kind(artifact) == "preview"
                and _artifact_mentions(artifact, ("bed", "fit"))
            ],
            *[
                artifact
                for stage in bed_stages
                for artifact in _as_list(stage.get("artifacts"))
                if isinstance(stage, Mapping)
            ],
        ]
    )
    body = "\n".join(
        [
            _render_artifact_cards(
                bed_artifacts,
                layout=layout,
                empty="No bed-fit preview recorded yet.",
            ),
            _render_stage_cards(bed_stages),
        ]
    )
    return _section("Bed Fit", body, classes=("section-bed-fit",))


def _render_stages(stages: list[Any], *, layout: RunLayout | None) -> str:
    if not stages:
        return _section("Stages", "<p>No stages recorded yet.</p>")

    rows = [
        "      <thead>",
        "        <tr>",
        "          <th>Stage</th>",
        "          <th>Status</th>",
        "          <th>Message</th>",
        "          <th>Artifacts</th>",
        "          <th>Metrics</th>",
        "        </tr>",
        "      </thead>",
        "      <tbody>",
    ]
    for stage in stages:
        if not isinstance(stage, Mapping):
            rows.append(f"        <tr><td colspan=\"5\">{_render_value(stage)}</td></tr>")
            continue

        status_value = str(stage.get("status", "unknown"))
        status = _as_text(status_value)
        status_class = _class_name(status_value)
        rows.extend(
            [
                "        <tr>",
                f"          <td>{_as_text(stage.get('stage', 'unknown'))}</td>",
                (
                    "          <td>"
                    f'<span class="status status-{status_class}">{status}</span>'
                    "</td>"
                ),
                f"          <td>{_as_text(stage.get('message', ''))}</td>",
                "          <td>",
                _render_artifact_links(_as_list(stage.get("artifacts")), layout=layout),
                "          </td>",
                f"          <td>{_render_value(stage.get('metrics', {}))}</td>",
                "        </tr>",
            ]
        )

    rows.extend(["      </tbody>"])
    return _section("Stages", '<table class="stages">\n' + "\n".join(rows) + "\n    </table>")


def _render_artifacts(artifacts: list[Any], *, layout: RunLayout | None) -> str:
    if not artifacts:
        return _section("Artifacts", "<p>No artifacts recorded yet.</p>")
    return _section("Artifacts", _render_artifact_links(artifacts, layout=layout))


def _render_slice_summary(
    stages: list[Any],
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
) -> str:
    slice_stages = [
        stage
        for stage in stages
        if isinstance(stage, Mapping) and "slice" in str(stage.get("stage", "")).lower()
    ]
    if not slice_stages:
        return _section(
            "Slice Summary",
            '<p class="empty-note">Slice summary pending final slice gate integration.</p>',
            classes=("section-slice-summary",),
        )

    slice_artifacts = _artifacts_with_kinds(artifacts, {"3mf", "slice_log"})
    body = "\n".join(
        [
            _render_slice_metrics(slice_stages),
            _render_stage_cards(slice_stages),
            _render_artifact_cards(
                slice_artifacts,
                layout=layout,
                empty="No slice artifacts recorded yet.",
            ),
        ]
    )
    return _section("Slice Summary", body, classes=("section-slice-summary",))


def _render_list_section(title: str, values: list[Any], *, empty: str) -> str:
    if not values:
        return _section(title, f"<p>{_as_text(empty)}</p>")
    items = [f"      <li>{_render_value(value)}</li>" for value in values]
    return _section(title, "<ul>\n" + "\n".join(items) + "\n    </ul>")


def _render_warnings_section(warnings: list[Any]) -> str:
    if not warnings:
        return _section(
            "Warnings",
            '<p class="empty-note">No warnings recorded.</p>',
            classes=("section-warnings",),
        )
    items = [f"      <li class=\"warning-item\">{_render_value(warning)}</li>" for warning in warnings]
    return _section(
        "Warnings",
        '<ul class="warning-list">\n' + "\n".join(items) + "\n    </ul>",
        classes=("section-warnings",),
    )


def _render_settings_changes_section(settings_changes: list[Any]) -> str:
    if not settings_changes:
        return _section(
            "Settings Changes",
            '<p class="empty-note">No settings changes recorded.</p>',
            classes=("section-settings-changes",),
        )

    items = [
        f"      <li class=\"settings-change\">{_render_settings_change(change)}</li>"
        for change in settings_changes
    ]
    return _section(
        "Settings Changes",
        '<ul class="settings-list">\n' + "\n".join(items) + "\n    </ul>",
        classes=("section-settings-changes",),
    )


def _render_pre_print_checklist_section(pre_print_checklist: list[Any]) -> str:
    if not pre_print_checklist:
        return _section(
            "Pre-print Checklist",
            '<p class="empty-note">Pre-print checklist pending final slice gate integration.</p>',
            classes=("section-pre-print-checklist",),
        )

    items = [
        f"      {_render_checklist_item(item)}"
        for item in pre_print_checklist
    ]
    return _section(
        "Pre-print Checklist",
        '<ul class="checklist">\n' + "\n".join(items) + "\n    </ul>",
        classes=("section-pre-print-checklist",),
    )


def _render_stage_cards(stages: list[Any]) -> str:
    if not stages:
        return ""

    cards = []
    for stage in stages:
        if not isinstance(stage, Mapping):
            cards.append(f'      <article class="stage-card">{_render_value(stage)}</article>')
            continue

        stage_name = _as_text(stage.get("stage", "unknown"))
        status_value = str(stage.get("status", "unknown"))
        status_class = _class_name(status_value)
        message = _as_text(stage.get("message", ""))
        metrics = stage.get("metrics", {})
        metrics_html = ""
        if metrics:
            metrics_html = f'\n        <div class="stage-metrics">{_render_value(metrics)}</div>'
        cards.append(
            "      <article "
            f'class="stage-card stage-{_class_name(str(stage.get("stage", "unknown")))}">'
            f"<h3>{stage_name}</h3>"
            f'<span class="status status-{status_class}">{_as_text(status_value)}</span>'
            f"<p>{message}</p>"
            f"{metrics_html}"
            "</article>"
        )

    return '<div class="stage-card-grid">\n' + "\n".join(cards) + "\n    </div>"


def _render_slice_metrics(slice_stages: list[Any]) -> str:
    metrics = []
    for stage in slice_stages:
        if not isinstance(stage, Mapping):
            continue
        stage_metrics = stage.get("metrics", {})
        if isinstance(stage_metrics, Mapping):
            metrics.extend(stage_metrics.items())
        elif stage_metrics:
            metrics.append(("summary", stage_metrics))

    if not metrics:
        return '<p class="empty-note">No slice metrics recorded yet.</p>'

    cards = [
        "      <div class=\"slice-metric\">"
        f"<dt>{_as_text(key)}</dt>"
        f"<dd>{_render_value(value)}</dd>"
        "</div>"
        for key, value in metrics
    ]
    return '<dl class="slice-metric-grid">\n' + "\n".join(cards) + "\n    </dl>"


def _render_artifact_cards(
    artifacts: list[Any],
    *,
    layout: RunLayout | None,
    empty: str,
) -> str:
    if not artifacts:
        return f'<p class="empty-note">{_as_text(empty)}</p>'

    cards = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            cards.append(f'      <article class="artifact-card">{_render_value(artifact)}</article>')
            continue

        path = artifact.get("path", "")
        href = _artifact_href(path, layout=layout)
        label = artifact.get("label") or path or "Artifact"
        kind = artifact.get("kind", "artifact")
        kind_class = _class_name(str(kind))
        card_classes = " ".join(_artifact_card_classes(kind_class))
        download_attribute = _download_attribute(kind, path)
        preview_html = _render_preview_embed(
            kind=kind,
            href=href,
            label=label,
            path=path,
        )
        metadata = artifact.get("metadata", {})
        metadata_html = ""
        if metadata:
            metadata_html = f'\n        <div class="metadata">{_render_value(metadata)}</div>'
        cards.append(
            "      <article "
            f'class="{_as_attribute(card_classes)}">'
            f'<h3><a href="{_as_attribute(href)}"{download_attribute}>'
            f"{_as_text(label)}</a></h3>"
            f'<span class="kind">{_as_text(kind)}</span>'
            f' <code>{_as_text(path)}</code>'
            f"{preview_html}"
            f"{metadata_html}"
            "</article>"
        )

    return '<div class="artifact-card-grid">\n' + "\n".join(cards) + "\n    </div>"


def _render_artifact_links(artifacts: list[Any], *, layout: RunLayout | None) -> str:
    if not artifacts:
        return "<p>None recorded.</p>"

    items = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            items.append(f"      <li>{_render_value(artifact)}</li>")
            continue

        path = artifact.get("path", "")
        href = _artifact_href(path, layout=layout)
        label = artifact.get("label") or path or "Artifact"
        kind = artifact.get("kind", "artifact")
        metadata = artifact.get("metadata", {})
        metadata_html = ""
        if metadata:
            metadata_html = f"\n        <div class=\"metadata\">{_render_value(metadata)}</div>"
        items.append(
            "      <li>"
            f'<a href="{_as_attribute(href)}">{_as_text(label)}</a>'
            f' <span class="kind">{_as_text(kind)}</span>'
            f' <code>{_as_text(path)}</code>'
            f"{metadata_html}"
            "</li>"
        )
    return "<ul>\n" + "\n".join(items) + "\n    </ul>"


def _artifact_card_classes(kind_class: str) -> tuple[str, ...]:
    extra_classes = []
    if kind_class == "preview":
        extra_classes.append("artifact-preview-card")
    if kind_class == "3mf":
        extra_classes.append("artifact-print-bundle")
    if kind_class == "slice-log":
        extra_classes.append("artifact-slice-artifact")
    return ("artifact-card", f"artifact-{kind_class}", *extra_classes)


def _download_attribute(kind: Any, path: Any) -> str:
    if str(kind) != "3mf":
        return ""
    filename = Path(str(path)).name
    if not filename:
        return ""
    return f' download="{_as_attribute(filename)}"'


def _render_preview_embed(*, kind: Any, href: str, label: Any, path: Any) -> str:
    if str(kind) != "preview" or not _is_safe_local_href(href):
        return ""

    suffix = Path(str(path)).suffix.lower()
    title = f"Preview: {label}"
    if suffix in {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return (
            '\n        <a class="artifact-preview-frame" '
            f'href="{_as_attribute(href)}">'
            '<img class="artifact-preview-embed" '
            f'src="{_as_attribute(href)}" alt="{_as_attribute(title)}">'
            "</a>"
        )
    if suffix in {".html", ".htm"}:
        return (
            '\n        <iframe class="artifact-preview-embed" '
            f'src="{_as_attribute(href)}" title="{_as_attribute(title)}" '
            'loading="lazy" sandbox=""></iframe>'
        )
    return ""


def _is_safe_local_href(href: str) -> bool:
    href_lower = href.lower()
    return bool(href) and not (
        href_lower.startswith(("http://", "https://", "data:", "javascript:"))
        or href.startswith("//")
    )


def _render_settings_change(change: Any) -> str:
    if not isinstance(change, Mapping):
        return _render_value(change)

    label = (
        change.get("key")
        or change.get("setting")
        or change.get("name")
        or "Setting change"
    )
    details = []
    for key, title in (
        ("default", "Default"),
        ("previous", "Previous"),
        ("value", "Value"),
        ("reason", "Reason"),
    ):
        if key in change:
            details.append(
                "      <div>"
                f"<dt>{title}</dt>"
                f"<dd>{_render_value(change.get(key))}</dd>"
                "</div>"
            )
    if not details:
        return _render_value(change)

    return (
        f"<h3>{_as_text(label)}</h3>"
        '<dl class="key-values">\n'
        + "\n".join(details)
        + "\n    </dl>"
    )


def _first_prompt_reference_stage(stages: list[Any]) -> Mapping[str, Any] | None:
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        if str(stage.get("stage", "")) == "prompt_reference_generation":
            return stage
    return None


def _render_prompt_reference_items(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        "        <div>"
        f"<dt>{_as_text(label)}</dt>"
        f"<dd>{_as_text(value)}</dd>"
        "</div>"
        for label, value in items
    )


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


def _prompt_budget_label(stage: Mapping[str, Any], quote: Mapping[str, Any]) -> str:
    status = _prompt_budget_status(stage, quote)
    labels = {
        "blocked": "Budget blocked before remote work",
        "within_cap": "Within configured cap",
        "within_cap_pending": "Within cap; provider did not finish",
        "unchecked": "Cap set; estimate missing",
        "not_capped": "No max cost cap recorded",
    }
    return labels.get(status, "Review budget receipt")


def _prompt_budget_status(stage: Mapping[str, Any], quote: Mapping[str, Any]) -> str:
    message = str(stage.get("message", "")).lower()
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
    if str(stage.get("status", "")).lower() == "succeeded":
        return "within_cap"
    return "within_cap_pending"


def _remote_prompt_note(quote: Mapping[str, Any]) -> str:
    remote_upload = quote.get("remote_upload")
    stores_prompt = quote.get("stores_prompt_with_provider")
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


def _render_checklist_item(item: Any) -> str:
    if not isinstance(item, Mapping):
        return f'<li class="checklist-item checklist-status-pending">{_render_value(item)}</li>'

    status = str(item.get("status", "pending"))
    status_class = _class_name(status)
    label = (
        item.get("title")
        or item.get("item")
        or item.get("label")
        or item.get("text")
        or "Checklist item"
    )
    detail_items = {
        key: value
        for key, value in item.items()
        if key not in {"item", "label", "text", "title", "status"}
    }
    details = ""
    if detail_items:
        details = f'\n        <div class="checklist-details">{_render_value(detail_items)}</div>'

    return (
        f'<li class="checklist-item checklist-status-{status_class}">'
        f'<span class="checklist-status status-{status_class}">{_as_text(status)}</span>'
        f"<span>{_as_text(label)}</span>"
        f"{details}"
        "</li>"
    )


def _render_value(value: Any) -> str:
    if isinstance(value, Mapping):
        if not value:
            return ""
        items = []
        for key, nested_value in value.items():
            items.append(
                "      <div>"
                f"<dt>{_as_text(key)}</dt>"
                f"<dd>{_render_value(nested_value)}</dd>"
                "</div>"
            )
        return '<dl class="key-values">\n' + "\n".join(items) + "\n    </dl>"

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        if not value:
            return ""
        items = [f"      <li>{_render_value(item)}</li>" for item in value]
        return '<ul class="nested">\n' + "\n".join(items) + "\n    </ul>"

    return _as_text(value)


def _section(title: str, body: str, *, classes: Sequence[str] = ()) -> str:
    class_names = " ".join(["report-section", *classes])
    return "\n".join(
        [
            f'    <section class="{_as_attribute(class_names)}">',
            f"      <h2>{_as_text(title)}</h2>",
            f"    {body}",
            "    </section>",
        ]
    )


def _artifacts_with_kinds(artifacts: list[Any], kinds: set[str]) -> list[Any]:
    return [
        artifact
        for artifact in artifacts
        if _artifact_kind(artifact) in kinds
    ]


def _preview_artifacts_from_stages(stages: list[Any]) -> list[Any]:
    previews = []
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        for artifact in _as_list(stage.get("artifacts")):
            if _artifact_kind(artifact) == "preview":
                previews.append(artifact)
    return previews


def _artifact_kind(artifact: Any) -> str:
    if not isinstance(artifact, Mapping):
        return ""
    return str(artifact.get("kind", ""))


def _artifact_mentions(artifact: Any, terms: Sequence[str]) -> bool:
    if not isinstance(artifact, Mapping):
        return False
    searchable = " ".join(
        str(artifact.get(key, ""))
        for key in ("kind", "label", "path")
    ).lower()
    return any(term in searchable for term in terms)


def _stages_matching(stages: list[Any], terms: Sequence[str]) -> list[Any]:
    matches = []
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        stage_text = " ".join(
            [
                str(stage.get("stage", "")),
                str(stage.get("message", "")),
                _metric_keys_text(stage.get("metrics", {})),
            ]
        ).lower()
        if any(term in stage_text for term in terms):
            matches.append(stage)
    return matches


def _metric_keys_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(
            [
                str(key)
                for key in value
            ]
            + [
                _metric_keys_text(nested_value)
                for nested_value in value.values()
            ]
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return " ".join(_metric_keys_text(item) for item in value)
    return ""


def _unique_artifacts(artifacts: list[Any]) -> list[Any]:
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            unique.append(artifact)
            continue
        key = (
            str(artifact.get("kind", "")),
            str(artifact.get("path", "")),
            str(artifact.get("label", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(artifact)
    return unique


def _artifact_href(path: Any, *, layout: RunLayout | None) -> str:
    path_text = str(path)
    if layout is None:
        return _quote_url_path(path_text)

    artifact_path = Path(path_text)
    if not artifact_path.is_absolute():
        artifact_path = layout.root / artifact_path

    relative_path = os.path.relpath(
        artifact_path.expanduser().resolve(),
        start=layout.reports_dir.expanduser().resolve(),
    )
    return _quote_url_path(Path(relative_path).as_posix())


def _quote_url_path(path: str) -> str:
    return quote(path.replace(os.sep, "/"), safe="/.")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return list(value)
    return [value]


def _as_text(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _as_attribute(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _class_name(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character == "-" else "-"
        for character in value.lower()
    )
    return cleaned.strip("-") or "unknown"


_CSS = """
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
      color: #1f2933;
      background: #f7f8fa;
    }
    body {
      margin: 0;
    }
    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }
    header {
      margin-bottom: 28px;
    }
    header p {
      margin: 0 0 4px;
      color: #52606d;
      font-size: 0.92rem;
      text-transform: uppercase;
    }
    h1, h2 {
      margin: 0;
      line-height: 1.2;
    }
    h1 {
      font-size: 2rem;
    }
    h2 {
      font-size: 1.15rem;
      margin-bottom: 12px;
    }
    h3 {
      font-size: 0.98rem;
      margin: 0 0 6px;
    }
    .report-section {
      background: #ffffff;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }
    .artifact-card-grid,
    .stage-card-grid,
    .slice-metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin: 0;
    }
    .artifact-card,
    .stage-card,
    .slice-metric,
    .settings-change,
    .checklist-item,
    .warning-item {
      border: 1px solid #e4e7eb;
      border-radius: 6px;
      background: #fbfcfd;
      padding: 12px;
    }
    .artifact-card h3 {
      word-break: break-word;
    }
    .artifact-preview-frame,
    .artifact-preview-embed {
      display: block;
      width: 100%;
    }
    .artifact-preview-frame {
      margin-top: 10px;
    }
    .artifact-preview-embed {
      margin-top: 10px;
      min-height: 140px;
      max-height: 260px;
      object-fit: contain;
      border: 1px solid #e4e7eb;
      border-radius: 6px;
      background: #ffffff;
    }
    iframe.artifact-preview-embed {
      height: 220px;
    }
    .stage-card-grid {
      margin-top: 12px;
    }
    .stage-card p {
      margin: 8px 0 0;
    }
    .stage-metrics {
      border-top: 1px solid #e4e7eb;
      margin-top: 10px;
      padding-top: 10px;
    }
    .slice-metric {
      display: block;
    }
    .slice-metric dt {
      margin-bottom: 4px;
    }
    .prompt-reference-summary {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.74fr);
      gap: 16px;
      align-items: start;
    }
    .prompt-reference-summary p {
      margin: 8px 0 0;
    }
    .provider-note {
      color: #52606d;
      font-weight: 700;
    }
    .prompt-reference-grid {
      display: grid;
      grid-template-columns: max-content minmax(0, 1fr);
      gap: 6px 12px;
      margin: 0;
    }
    .prompt-reference-grid div {
      display: contents;
    }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border-bottom: 1px solid #e4e7eb;
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: #52606d;
      font-size: 0.86rem;
      font-weight: 700;
    }
    ul {
      margin: 0;
      padding-left: 20px;
    }
    .warning-list,
    .settings-list,
    .checklist {
      list-style: none;
      padding-left: 0;
    }
    li + li {
      margin-top: 8px;
    }
    a {
      color: #0b5cad;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    code {
      color: #52606d;
      font-size: 0.88rem;
      word-break: break-word;
    }
    .kind, .status {
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 0.78rem;
      font-weight: 700;
    }
    .kind {
      background: #edf2f7;
      color: #334e68;
    }
    .status {
      background: #edf2f7;
      color: #334e68;
    }
    .status-succeeded {
      background: #e3f8ec;
      color: #147d64;
    }
    .status-failed {
      background: #ffe3e3;
      color: #ab091e;
    }
    .status-running {
      background: #fff3c4;
      color: #8d2b0b;
    }
    .status-pending {
      background: #edf2f7;
      color: #334e68;
    }
    .status-skipped {
      background: #e6e6ff;
      color: #3f3cbb;
    }
    .checklist-item {
      display: grid;
      grid-template-columns: max-content minmax(0, 1fr);
      gap: 8px 10px;
      align-items: start;
    }
    .checklist-details {
      grid-column: 2;
    }
    .key-values {
      display: grid;
      grid-template-columns: max-content minmax(0, 1fr);
      gap: 4px 10px;
      margin: 0;
    }
    .key-values div {
      display: contents;
    }
    dt {
      color: #52606d;
      font-weight: 700;
    }
    dd {
      margin: 0;
    }
    .metadata {
      margin-top: 6px;
    }
    .nested {
      margin-top: 4px;
    }
    .empty-note {
      color: #52606d;
      margin: 0;
    }
    @media (max-width: 720px) {
      main {
        padding: 20px 12px 40px;
      }
      th, td {
        padding: 8px;
      }
      .checklist-item {
        grid-template-columns: 1fr;
      }
      .checklist-details {
        grid-column: auto;
      }
      .prompt-reference-summary,
      .prompt-reference-grid {
        grid-template-columns: 1fr;
      }
    }
""".strip()


__all__ = ["render_html_report", "write_html_report"]
