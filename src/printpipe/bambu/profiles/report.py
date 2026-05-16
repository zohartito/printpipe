"""Settings delta report writers for Bambu profile changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

MISSING_REASON = "reason not assigned"


def summarize_delta_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize settings delta rows by category and reason coverage."""
    total = 0
    missing_reasons = 0
    by_category: dict[str, int] = {}

    for row in rows:
        total += 1
        category = str(row.get("category") or "uncategorized")
        by_category[category] = by_category.get(category, 0) + 1
        if _is_missing_reason(row.get("reason")):
            missing_reasons += 1

    return {
        "total": total,
        "by_category": dict(sorted(by_category.items())),
        "missing_reasons": missing_reasons,
    }


def write_settings_delta_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
    title: str = "Bambu Settings Delta Report",
) -> tuple[Path, Path]:
    """Write settings delta rows to JSON and Markdown report files."""
    json_output_path = Path(json_path)
    markdown_output_path = Path(markdown_path)
    row_list = [dict(row) for row in rows]
    payload = {
        "summary": summarize_delta_rows(row_list),
        "rows": row_list,
    }

    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.write_text(
        _render_markdown(row_list, payload["summary"], title=title),
        encoding="utf-8",
    )

    return json_output_path, markdown_output_path


def _render_markdown(
    rows: list[dict[str, Any]],
    summary: Mapping[str, Any],
    *,
    title: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"Total changed settings: {summary['total']}",
        f"Rows missing assigned reasons: {summary['missing_reasons']}",
        "",
        "## Category Counts",
    ]

    by_category = summary.get("by_category", {})
    if by_category:
        for category, count in by_category.items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Settings Changes",
        ]
    )

    if not rows:
        lines.append("No settings changes recorded.")
    else:
        lines.extend(
            [
                "| Key | Default | Custom | Category | Reason |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in rows:
            lines.append(
                " | ".join(
                    [
                        f"| {_escape_cell(row.get('key', ''))}",
                        _format_value(row.get("default")),
                        _format_value(row.get("custom")),
                        _escape_cell(row.get("category", "")),
                        f"{_escape_cell(row.get('reason', ''))} |",
                    ]
                )
            )

    return "\n".join(lines) + "\n"


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, sort_keys=True)
    return f"`{_escape_cell(rendered)}`"


def _escape_cell(value: Any) -> str:
    text = str(value).replace("\n", "<br>")
    return text.replace("|", "\\|")


def _is_missing_reason(reason: Any) -> bool:
    if not isinstance(reason, str):
        return True
    return reason.strip().lower() in {"", MISSING_REASON}
