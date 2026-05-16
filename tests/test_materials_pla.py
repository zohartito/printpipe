from __future__ import annotations

import json

import pytest

from printpipe.bambu.profiles.core import generate_settings_delta_rows
from printpipe.materials.pla import PLA_RULES, build_pla_overrides


def test_pla_rules_define_plain_and_plus_profile_intents():
    assert set(PLA_RULES) == {"pla", "pla_plus"}

    plain = build_pla_overrides("pla")
    plus = build_pla_overrides("pla+")

    assert plain["variant"] == "pla"
    assert plus["variant"] == "pla_plus"
    assert "Generic PLA" in plain["profile_intent"]
    assert "PLA+" in plus["profile_intent"]


def test_build_pla_overrides_returns_filament_and_process_rules_with_reasons():
    result = build_pla_overrides()

    assert result["filament_overrides"]["filament_type"] == ["PLA"]
    assert result["process_overrides"]["layer_height"] == ["0.20"]
    assert result["process_overrides"]["wall_loops"] == ["2"]

    emitted_keys = set(result["filament_overrides"]) | set(result["process_overrides"])
    assert emitted_keys <= set(result["reasons"])
    assert all(result["reasons"][key].strip() for key in emitted_keys)


def test_build_pla_overrides_returns_independent_copies():
    first = build_pla_overrides()
    second = build_pla_overrides()

    first["filament_overrides"]["filament_type"].append("MUTATED")
    first["reasons"]["layer_height"] = "changed"

    assert second["filament_overrides"]["filament_type"] == ["PLA"]
    assert second["reasons"]["layer_height"] != "changed"


def test_pla_rules_do_not_leak_tpu_specific_profile_keys_or_claims():
    tpu_specific_keys = {
        "enable_pressure_advance",
        "pressure_advance",
        "filament_max_volumetric_speed",
        "filament_retract_length",
        "filament_retract_lift",
        "filament_retract_speed",
        "support_style",
        "support_type",
    }

    for variant in ("pla", "pla+"):
        result = build_pla_overrides(variant)
        emitted_keys = set(result["filament_overrides"]) | set(result["process_overrides"])

        assert emitted_keys.isdisjoint(tpu_specific_keys)
        assert "TPU" not in json.dumps(result, sort_keys=True).upper()


def test_pla_overrides_can_feed_settings_delta_rows_with_reasons():
    result = build_pla_overrides()
    custom = {
        **result["filament_overrides"],
        **result["process_overrides"],
    }
    defaults = {
        "filament_type": ["ABS"],
        "filament_vendor": ["Unknown"],
        "layer_height": ["0.16"],
        "wall_loops": ["3"],
    }

    rows = generate_settings_delta_rows(
        defaults,
        custom,
        categories=result["categories"],
        reasons=result["reasons"],
        extruder_count=1,
    )

    assert {row["key"] for row in rows} == set(custom)
    assert all(row["reason"] != "reason not assigned" for row in rows)
    assert {row["category"] for row in rows} == {"compatibility", "metadata"}


def test_unknown_pla_variant_lists_supported_variants():
    with pytest.raises(ValueError, match="pla, pla_plus"):
        build_pla_overrides("silk")
