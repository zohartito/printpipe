from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from printpipe.bambu.profiles import (
    EnumValidationError,
    generate_settings_delta_rows,
    load_profile,
    load_profile_map,
    resolve_inherits,
    settings_equal,
    validate_enum_value,
)


def test_load_profile_reads_json_from_path(tmp_path: Path):
    profile_path = tmp_path / "pla.json"
    profile_path.write_text(json.dumps({"name": "Generic PLA", "type": "filament"}))

    assert load_profile(profile_path) == {"name": "Generic PLA", "type": "filament"}


def test_load_profile_map_indexes_profiles_by_name(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps({"name": "Base"}))
    second.write_text(json.dumps({"name": "Leaf"}))

    profiles = load_profile_map([first, second])

    assert profiles == {
        "Base": {"name": "Base"},
        "Leaf": {"name": "Leaf"},
    }


def test_resolve_inherits_flattens_parent_to_child_without_mutating_inputs():
    base = {
        "name": "fdm_process_common",
        "support_style": "default",
        "speed": ["40"],
        "wall_loops": ["2"],
        "nested": {"parent": "kept", "overridden": "base"},
    }
    child = {
        "name": "0.20mm Slipper TPU 90A @BBL P2S",
        "inherits": "fdm_process_common",
        "from": "User",
        "type": "process",
        "speed": ["30"],
        "nested": {"overridden": "child"},
    }
    profiles = {base["name"]: base, child["name"]: child}
    original_profiles = copy.deepcopy(profiles)

    resolved = resolve_inherits(child, profiles=profiles)

    assert resolved == {
        "name": "0.20mm Slipper TPU 90A @BBL P2S",
        "support_style": "default",
        "speed": ["30"],
        "wall_loops": ["2"],
        "nested": {"parent": "kept", "overridden": "child"},
    }
    assert profiles == original_profiles


def test_resolve_inherits_accepts_resolver_callback():
    root = {"name": "root", "speed": "20"}
    leaf = {"name": "leaf", "inherits": "root", "speed": "25"}

    resolved = resolve_inherits(leaf, resolver=lambda name: root if name == "root" else None)

    assert resolved["speed"] == "25"


def test_resolve_inherits_detects_cycles():
    profiles = {
        "a": {"name": "a", "inherits": "b"},
        "b": {"name": "b", "inherits": "a"},
    }

    with pytest.raises(ValueError, match="inheritance cycle"):
        resolve_inherits(profiles["a"], profiles=profiles)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (["0.20"], "0.2"),
        (["225", "225"], ["225"]),
        ("20%", ["20.0%"]),
        (["nil"], "nil"),
    ],
)
def test_settings_equal_normalizes_singletons_and_numeric_formatting(left, right):
    assert settings_equal(left, right, extruder_count=1)


def test_settings_delta_rows_skip_normalized_no_ops_and_attach_reasons():
    defaults = {
        "support_style": "default",
        "layer_height": ["0.20"],
        "slow_down_layer_time": "nil",
        "wall_loops": ["2"],
    }
    custom = {
        "support_style": "snug",
        "layer_height": "0.2",
        "slow_down_layer_time": ["nil"],
        "wall_loops": ["3"],
    }

    rows = generate_settings_delta_rows(
        defaults,
        custom,
        categories={"support_style": "behavior"},
        reasons={"support_style": "TPU supports should be easier to peel."},
        extruder_count=1,
    )

    assert rows == [
        {
            "key": "support_style",
            "default": "default",
            "custom": "snug",
            "category": "behavior",
            "reason": "TPU supports should be easier to peel.",
        },
        {
            "key": "wall_loops",
            "default": ["2"],
            "custom": ["3"],
            "category": "behavior",
            "reason": "reason not assigned",
        },
    ]


def test_validate_support_style_accepts_default_and_snug():
    assert validate_enum_value("support_style", "default") == "default"
    assert validate_enum_value("support_style", ["snug"]) == "snug"


def test_validate_support_style_rejects_organic():
    with pytest.raises(EnumValidationError, match="support_style"):
        validate_enum_value("support_style", "organic")
