"""Tests for the `slicer-settings` CLI command and `run --set` override parsing."""

from __future__ import annotations

import json

import pytest

from printpipe.cli import _parse_overrides, main


def test_parse_overrides_wraps_scalar_in_list():
    assert _parse_overrides(["wall_loops=4"]) == {"wall_loops": ["4"]}


def test_parse_overrides_splits_comma_values():
    assert _parse_overrides(["outer_wall_speed=200,500"]) == {
        "outer_wall_speed": ["200", "500"]
    }


def test_parse_overrides_rejects_missing_equals():
    with pytest.raises(ValueError):
        _parse_overrides(["wall_loops"])


def test_parse_overrides_rejects_empty_key():
    with pytest.raises(ValueError):
        _parse_overrides(["=4"])


def test_slicer_settings_json_filtered_keys(capsys):
    code = main(
        [
            "slicer-settings",
            "Bambu PLA Basic",
            "--key",
            "wall_loops",
            "--key",
            "enable_support",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"wall_loops", "enable_support"}


def test_slicer_settings_human_lists_process_group(capsys):
    code = main(["slicer-settings", "Bambu PLA Basic"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[process]" in out
    assert "enable_support" in out
