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
            _render_stages(stages, layout=layout),
            _render_artifacts(artifacts, layout=layout),
            _render_slice_summary(stages),
            _render_list_section("Warnings", warnings, empty="No warnings recorded."),
            _render_list_section(
                "Settings Changes",
                settings_changes,
                empty="No settings changes recorded.",
            ),
            _render_list_section(
                "Pre-print Checklist",
                pre_print_checklist,
                empty="Pre-print checklist pending final slice gate integration.",
            ),
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


def _render_slice_summary(stages: list[Any]) -> str:
    slice_stages = [
        stage
        for stage in stages
        if isinstance(stage, Mapping) and "slice" in str(stage.get("stage", "")).lower()
    ]
    if not slice_stages:
        return _section(
            "Slice Summary",
            "<p>Slice summary pending final slice gate integration.</p>",
        )

    items = [
        f"      <li>{_render_value(stage.get('metrics', {}))}</li>"
        for stage in slice_stages
    ]
    return _section("Slice Summary", "<ul>\n" + "\n".join(items) + "\n    </ul>")


def _render_list_section(title: str, values: list[Any], *, empty: str) -> str:
    if not values:
        return _section(title, f"<p>{_as_text(empty)}</p>")
    items = [f"      <li>{_render_value(value)}</li>" for value in values]
    return _section(title, "<ul>\n" + "\n".join(items) + "\n    </ul>")


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


def _section(title: str, body: str) -> str:
    return "\n".join(
        [
            '    <section class="report-section">',
            f"      <h2>{_as_text(title)}</h2>",
            f"    {body}",
            "    </section>",
        ]
    )


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
    .report-section {
      background: #ffffff;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
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
""".strip()


__all__ = ["render_html_report", "write_html_report"]
