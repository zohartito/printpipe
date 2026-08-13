"""Tests for the `slicer-settings` CLI command and `run --set` override parsing."""

from __future__ import annotations

import json

import pytest

from printpipe.cli import _parse_overrides, main
from printpipe.pipeline import resolve_slice_settings


def _rich_slicer_keyspace_available() -> bool:
    """True when a real Bambu/Orca profile source resolves the full keyspace.

    The full process keyspace (including ``enable_support``) is sourced from an
    installed Bambu Studio / OrcaSlicer profile tree. CI runners have no slicer
    installed, so only a minimal fallback profile is available there and tests
    that assert the rich keyspace must skip.
    """
    try:
        return "enable_support" in resolve_slice_settings("Bambu PLA Basic")["process"]
    except Exception:  # noqa: BLE001 - any resolution failure means no rich keyspace
        return False


requires_slicer_profiles = pytest.mark.skipif(
    not _rich_slicer_keyspace_available(),
    reason="requires an installed Bambu Studio / OrcaSlicer profile tree (not present in CI)",
)


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


@requires_slicer_profiles
def test_slicer_settings_human_lists_process_group(capsys):
    code = main(["slicer-settings", "Bambu PLA Basic"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[process]" in out
    assert "enable_support" in out
