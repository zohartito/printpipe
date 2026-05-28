from __future__ import annotations

from printpipe.bambu.profiles.core import generate_settings_delta_rows
from printpipe.materials.petg import PETG_RULES, build_petg_overrides


def test_petg_rules_define_default_foundation():
    assert set(PETG_RULES) == {"petg-foundation"}

    result = build_petg_overrides()

    assert result["material_id"] == "petg-foundation"
    assert "Generic PETG" in result["profile_intent"]
    assert result["validation_status"] == "defaults-derived/unvalidated"


def test_petg_overrides_cover_foundation_categories_with_reasons():
    result = build_petg_overrides()

    assert result["filament_overrides"]["filament_type"] == ["PETG"]
    assert result["filament_overrides"]["textured_plate_temp_initial_layer"] == ["70"]
    assert result["filament_overrides"]["fan_max_speed"] == ["60"]
    assert result["filament_overrides"]["filament_max_volumetric_speed"] == ["8"]
    assert result["process_overrides"]["reduce_crossing_wall"] == "1"
    assert result["process_overrides"]["curr_bed_type"] == "Textured PEI Plate"

    custom_keys = set(result["filament_overrides"]) | set(result["process_overrides"])

    assert custom_keys <= set(result["reasons"])
    assert custom_keys <= set(result["categories"])
    assert all(result["reasons"][key].strip() for key in custom_keys)
    assert {
        "bed_adhesion",
        "cooling",
        "mvs_speed",
        "stringing_retraction",
    } <= set(result["categories"].values())
    assert any("unvalidated" in reason for reason in result["reasons"].values())


def test_petg_overrides_return_independent_copies():
    first = build_petg_overrides()
    second = build_petg_overrides()

    first["filament_overrides"]["filament_type"].append("MUTATED")
    first["process_overrides"]["outer_wall_speed"].append("MUTATED")
    first["reasons"]["fan_max_speed"] = "changed"

    assert second["filament_overrides"]["filament_type"] == ["PETG"]
    assert second["process_overrides"]["outer_wall_speed"] == ["100"]
    assert "unvalidated" in second["reasons"]["fan_max_speed"]


def test_petg_overrides_can_feed_settings_delta_rows_with_reasons():
    result = build_petg_overrides()
    custom = {
        **result["filament_overrides"],
        **result["process_overrides"],
    }

    rows = generate_settings_delta_rows(
        {},
        custom,
        categories=result["categories"],
        reasons=result["reasons"],
        extruder_count=1,
    )

    assert {row["key"] for row in rows} == set(custom)
    assert all(row["reason"] != "reason not assigned" for row in rows)
    assert {
        "bed_adhesion",
        "cooling",
        "mvs_speed",
        "stringing_retraction",
    } <= {row["category"] for row in rows}
