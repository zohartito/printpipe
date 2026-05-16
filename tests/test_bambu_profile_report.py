from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.profiles.core import generate_settings_delta_rows
from printpipe.bambu.profiles.report import summarize_delta_rows, write_settings_delta_report


def test_write_settings_delta_report_writes_json_and_markdown(tmp_path: Path):
    defaults = {
        "layer_height": ["0.20"],
        "nozzle_temperature": ["225", "225"],
        "slow_down_layer_time": "nil",
        "support_style": "default",
        "wall_loops": ["2"],
    }
    custom = {
        "layer_height": "0.2",
        "nozzle_temperature": ["225"],
        "slow_down_layer_time": ["nil"],
        "support_style": "snug",
        "wall_loops": ["3"],
    }
    rows = generate_settings_delta_rows(
        defaults,
        custom,
        categories={
            "support_style": "behavior",
            "wall_loops": "compatibility",
        },
        reasons={"support_style": "Use snug supports for TPU cleanup."},
        extruder_count=1,
    )

    json_path = tmp_path / "settings_delta.json"
    markdown_path = tmp_path / "settings_delta.md"

    written_paths = write_settings_delta_report(
        rows,
        json_path=json_path,
        markdown_path=markdown_path,
    )

    assert written_paths == (json_path, markdown_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload == {
        "summary": {
            "total": 2,
            "by_category": {
                "behavior": 1,
                "compatibility": 1,
            },
            "missing_reasons": 1,
        },
        "rows": [
            {
                "key": "support_style",
                "default": "default",
                "custom": "snug",
                "category": "behavior",
                "reason": "Use snug supports for TPU cleanup.",
            },
            {
                "key": "wall_loops",
                "default": ["2"],
                "custom": ["3"],
                "category": "compatibility",
                "reason": "reason not assigned",
            },
        ],
    }

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Bambu Settings Delta Report" in markdown
    assert "| Key | Default | Custom | Category | Reason |" in markdown
    assert "| support_style | `default` | `snug` | behavior | Use snug supports for TPU cleanup. |" in markdown
    assert "| wall_loops | `[\"2\"]` | `[\"3\"]` | compatibility | reason not assigned |" in markdown
    assert "Total changed settings: 2" in markdown
    assert "Rows missing assigned reasons: 1" in markdown
    assert "layer_height" not in markdown
    assert "nozzle_temperature" not in markdown
    assert "slow_down_layer_time" not in markdown


def test_summarize_delta_rows_counts_categories_and_missing_reasons():
    rows = [
        {
            "key": "support_style",
            "default": "default",
            "custom": "snug",
            "category": "behavior",
            "reason": "TPU supports should peel cleanly.",
        },
        {
            "key": "wall_loops",
            "default": ["2"],
            "custom": ["3"],
            "category": "behavior",
            "reason": "reason not assigned",
        },
        {
            "key": "filament_notes",
            "default": "",
            "custom": "SUNLU TPU 90A",
            "category": "metadata",
            "reason": "",
        },
    ]

    assert summarize_delta_rows(rows) == {
        "total": 3,
        "by_category": {
            "behavior": 2,
            "metadata": 1,
        },
        "missing_reasons": 2,
    }
