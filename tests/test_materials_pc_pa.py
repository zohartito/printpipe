from __future__ import annotations

import pytest

from printpipe.bambu.profiles import generate_settings_delta_rows
from printpipe.bambu.profiles.report import summarize_delta_rows
from printpipe.materials.pc_pa import get_material_rule


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("pc", "PC"),
        ("polycarbonate", "PC"),
        ("pa", "PA"),
        ("nylon", "PA"),
        ("pa-cf", "PA-CF"),
        ("nylon cf", "PA-CF"),
    ],
)
def test_get_material_rule_accepts_pc_pa_aliases(requested: str, expected: str):
    rule = get_material_rule(requested)

    assert rule.material == expected


def test_pc_pa_and_pa_cf_have_distinct_preflight_notes():
    pc = get_material_rule("pc")
    pa = get_material_rule("pa")
    pa_cf = get_material_rule("pa-cf")

    pc_messages = {note.message for note in pc.preflight_notes}
    pa_messages = {note.message for note in pa.preflight_notes}
    pa_cf_messages = {note.message for note in pa_cf.preflight_notes}

    assert pc_messages != pa_messages
    assert pa_messages != pa_cf_messages
    assert any("dry" in message.lower() for message in pc_messages)
    assert any(note.severity == "hard_gate" for note in pa.preflight_notes)
    assert any("moisture" in note.message.lower() for note in pa.preflight_notes)
    assert any("hardened nozzle" in message.lower() for message in pa_cf_messages)


@pytest.mark.parametrize("requested", ["pc", "pa", "pa-cf"])
def test_pc_pa_rule_settings_have_foundation_categories_and_reasons(requested: str):
    rule = get_material_rule(requested)
    overrides = rule.profile_overrides()
    required_categories = {
        "bed_adhesion",
        "chamber_preheat",
        "cooling",
        "strength_shell",
    }

    assert required_categories.issubset(set(rule.setting_categories.values()))
    assert set(overrides) <= set(rule.setting_categories)
    assert set(overrides) <= set(rule.setting_reasons)
    assert all(rule.setting_reasons[key].strip() for key in overrides)


def test_pa_cf_rule_output_can_feed_settings_delta_rows():
    rule = get_material_rule("pa-cf")
    defaults = {
        "bottom_shell_layers": "3",
        "brim_object_gap": "0.1",
        "brim_type": "no_brim",
        "brim_width": "5",
        "chamber_temperatures": ["0"],
        "fan_max_speed": ["100"],
        "fan_min_speed": ["40"],
        "filament_max_volumetric_speed": ["12"],
        "filament_type": ["PA"],
        "nozzle_temperature": ["260"],
        "overhang_fan_speed": ["95"],
        "sparse_infill_density": "15%",
        "textured_plate_temp": ["0"],
        "top_shell_layers": "3",
        "wall_loops": "2",
    }

    rows = generate_settings_delta_rows(
        defaults,
        rule.profile_overrides(),
        categories=rule.setting_categories,
        reasons=rule.setting_reasons,
        extruder_count=1,
    )

    summary = summarize_delta_rows(rows)
    changed_keys = {row["key"] for row in rows}

    assert "brim_type" in changed_keys
    assert "filament_type" in changed_keys
    assert "wall_loops" in changed_keys
    assert summary["missing_reasons"] == 0
    assert summary["by_category"]["bed_adhesion"] >= 1
    assert summary["by_category"]["cooling"] >= 1
    assert summary["by_category"]["strength_shell"] >= 1
