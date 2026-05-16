from __future__ import annotations

from printpipe.bambu.profiles import generate_settings_delta_rows
from printpipe.materials.tpu import available_tpu_rules, get_tpu_rule


def test_tpu_rule_catalog_defines_90a_and_95a_foundations():
    rules = available_tpu_rules()

    assert set(rules) >= {"tpu-90a-foundation", "tpu-95a-foundation"}
    assert rules["tpu-90a-foundation"].family == "TPU"
    assert rules["tpu-90a-foundation"].shore_hardness == "90A"
    assert rules["tpu-95a-foundation"].family == "TPU"
    assert rules["tpu-95a-foundation"].shore_hardness == "95A"


def test_sunlu_tpu_90a_slipper_rule_preserves_key_slipper_lessons():
    rule = get_tpu_rule("sunlu-tpu-90a-slipper")

    assert rule.shore_hardness == "90A"
    assert rule.filament_overrides["filament_max_volumetric_speed"] == ["2.5"]
    assert rule.filament_overrides["pressure_advance"] == ["0.040"]
    assert rule.filament_overrides["enable_pressure_advance"] == ["1"]
    assert rule.filament_overrides["fan_min_speed"] == ["30"]
    assert rule.filament_overrides["fan_max_speed"] == ["60"]
    assert rule.process_overrides["outer_wall_speed"] == ["25"]
    assert rule.process_overrides["top_surface_speed"] == ["20"]
    assert rule.process_overrides["support_style"] == ["snug"]
    assert rule.process_overrides["support_type"] == ["normal(auto)"]
    assert rule.process_overrides["support_top_z_distance"] == ["0.30"]
    assert rule.process_overrides["support_interface_top_layers"] == ["0"]
    assert rule.process_overrides["support_on_build_plate_only"] == ["1"]
    assert rule.process_overrides["brim_object_gap"] == ["0.12"]
    assert any("external spool" in note.lower() for note in rule.hardware_notes)
    assert any("ams" in note.lower() and "incompatible" in note.lower() for note in rule.hardware_notes)
    assert any("50 c" in note.lower() and "4-8 h" in note.lower() for note in rule.preflight_notes)
    assert "K = 0.040" in rule.reasons["pressure_advance"]
    assert "TPU-on-TPU" in rule.reasons["support_interface_top_layers"]


def test_sunlu_tpu_90a_rule_feeds_settings_delta_rows_with_reasons():
    rule = get_tpu_rule("sunlu-tpu-90a-slipper")
    custom = rule.combined_overrides()

    rows = generate_settings_delta_rows(
        {},
        custom,
        categories=rule.categories,
        reasons=rule.reasons,
        extruder_count=1,
    )

    keys = {row["key"] for row in rows}
    assert {"filament_max_volumetric_speed", "pressure_advance", "support_style"} <= keys
    assert len(rows) == len(custom)
    assert all(row["category"] in {"behavior", "compatibility", "metadata"} for row in rows)
    assert all(row["reason"] != "reason not assigned" for row in rows)
