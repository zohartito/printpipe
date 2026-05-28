from __future__ import annotations

from printpipe.bambu.profiles.core import generate_settings_delta_rows
from printpipe.materials.abs_asa import abs_rule, asa_rule, get_abs_asa_rule


def test_abs_and_asa_rules_expose_conservative_overrides_with_reasons():
    abs_material = abs_rule()
    asa_material = asa_rule()

    assert get_abs_asa_rule("ABS") == abs_material
    assert get_abs_asa_rule("asa") == asa_material

    assert abs_material.family == "ABS/ASA"
    assert asa_material.family == "ABS/ASA"
    assert abs_material.variant == "ABS"
    assert asa_material.variant == "ASA"

    assert abs_material.filament_overrides["filament_type"] == ["ABS"]
    assert asa_material.filament_overrides["filament_type"] == ["ASA"]
    assert abs_material.filament_overrides["nozzle_temperature"] != (
        asa_material.filament_overrides["nozzle_temperature"]
    )
    assert abs_material.filament_overrides["filament_max_volumetric_speed"] != (
        asa_material.filament_overrides["filament_max_volumetric_speed"]
    )
    assert abs_material.filament_overrides["fan_max_speed"] != (
        asa_material.filament_overrides["fan_max_speed"]
    )

    for material in (abs_material, asa_material):
        assert material.filament_overrides
        assert material.process_overrides
        assert set(material.override_keys()) == set(material.categories) == set(material.reasons)
        assert all(material.reasons[key].strip() for key in material.override_keys())


def test_preflight_notes_hold_chamber_ventilation_warping_and_preheat_guidance():
    for material in (abs_rule(), asa_rule()):
        note_categories = {note.category for note in material.preflight_notes}

        assert {"chamber", "ventilation", "warping", "preheat"}.issubset(note_categories)
        assert all(note.message.strip() for note in material.preflight_notes)

        override_key_text = " ".join(material.override_keys()).lower()
        assert "ventilation" not in override_key_text
        assert "vent" not in override_key_text
        assert "warping" not in override_key_text
        assert "preheat" not in override_key_text


def test_categories_cover_bed_adhesion_brim_and_cooling():
    for material in (abs_rule(), asa_rule()):
        category_values = set(material.categories.values())

        assert "bed_adhesion" in category_values
        assert "brim" in category_values
        assert "cooling" in category_values
        assert material.categories["textured_plate_temp"] == "bed_adhesion"
        assert material.categories["curr_bed_type"] == "bed_adhesion"
        assert material.categories["brim_width"] == "brim"
        assert material.categories["fan_max_speed"] == "cooling"
        assert material.process_overrides["curr_bed_type"] == "Textured PEI Plate"


def test_settings_delta_rows_can_consume_abs_asa_rule_output():
    defaults = {
        "brim_object_gap": "0",
        "brim_type": "no_brim",
        "brim_width": "0",
        "chamber_temperatures": ["0"],
        "fan_max_speed": ["80"],
        "fan_min_speed": ["10"],
        "filament_max_volumetric_speed": ["20"],
        "filament_type": ["PLA"],
        "hot_plate_temp": ["55"],
        "hot_plate_temp_initial_layer": ["55"],
        "nozzle_temperature": ["220"],
        "nozzle_temperature_initial_layer": ["220"],
        "slow_down_layer_time": ["3"],
        "textured_plate_temp": ["55"],
        "textured_plate_temp_initial_layer": ["55"],
    }

    for material in (abs_rule(), asa_rule()):
        rows = generate_settings_delta_rows(
            defaults,
            material.combined_overrides(),
            categories=material.categories,
            reasons=material.reasons,
            extruder_count=1,
        )

        assert rows
        assert {row["key"] for row in rows} == set(material.override_keys())
        assert {row["category"] for row in rows} >= {"bed_adhesion", "brim", "cooling"}
        assert all(row["reason"] != "reason not assigned" for row in rows)
