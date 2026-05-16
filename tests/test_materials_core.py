from __future__ import annotations

import pytest

from printpipe.bambu.profiles.report import summarize_delta_rows
from printpipe.materials import (
    MaterialRuleSet,
    get_material_rules,
    list_material_rules,
    material_delta_rows,
    register_material_rules,
)


def test_material_delta_rows_merge_overrides_and_keep_reason_catalog():
    rules = MaterialRuleSet(
        material_id="fake-flex",
        display_name="Fake Flex",
        base_profile_hint="Bambu TPU 90A @BBL P2S",
        filament_overrides={
            "filament_type": "TPU",
            "nozzle_temperature": ["230"],
        },
        process_overrides={
            "support_style": "snug",
            "wall_loops": ["3"],
        },
        reasons={
            "filament.nozzle_temperature": "Raise nozzle temperature for flexible filament flow.",
            "process.support_style": "Use snug supports for easier flexible-material cleanup.",
            "process.wall_loops": "Add perimeter strength for flexible parts.",
        },
        categories={
            "filament.nozzle_temperature": "behavior",
            "process.support_style": "behavior",
            "process.wall_loops": "compatibility",
        },
        preflight_notes=("Dry filament before printing.",),
    )

    filament_rows = material_delta_rows(
        {
            "filament_type": "TPU",
            "nozzle_temperature": ["220"],
        },
        rules,
        profile_scope="filament",
    )
    process_rows = material_delta_rows(
        {
            "support_style": "default",
            "wall_loops": ["2"],
        },
        rules,
        profile_scope="process",
    )

    assert filament_rows == [
        {
            "key": "nozzle_temperature",
            "default": ["220"],
            "custom": ["230"],
            "category": "behavior",
            "reason": "Raise nozzle temperature for flexible filament flow.",
            "profile_scope": "filament",
            "material_id": "fake-flex",
        },
    ]
    assert process_rows == [
        {
            "key": "support_style",
            "default": "default",
            "custom": "snug",
            "category": "behavior",
            "reason": "Use snug supports for easier flexible-material cleanup.",
            "profile_scope": "process",
            "material_id": "fake-flex",
        },
        {
            "key": "wall_loops",
            "default": ["2"],
            "custom": ["3"],
            "category": "compatibility",
            "reason": "Add perimeter strength for flexible parts.",
            "profile_scope": "process",
            "material_id": "fake-flex",
        },
    ]


def test_material_registry_registers_gets_and_lists_rule_sets():
    first = MaterialRuleSet(
        material_id="zz-fake-registry",
        display_name="ZZ Fake Registry",
        base_profile_hint="Generic PLA",
    )
    second = MaterialRuleSet(
        material_id="aa-fake-registry",
        display_name="AA Fake Registry",
        base_profile_hint="Generic PETG",
    )

    assert register_material_rules(first, replace=True) is first
    assert register_material_rules(second, replace=True) is second

    assert get_material_rules("zz-fake-registry") is first
    listed_ids = [rules.material_id for rules in list_material_rules()]
    assert listed_ids.index("aa-fake-registry") < listed_ids.index("zz-fake-registry")

    with pytest.raises(ValueError, match="already registered"):
        register_material_rules(first)
    with pytest.raises(KeyError, match="unknown material rule set"):
        get_material_rules("not-registered")


def test_material_delta_rows_missing_reasons_are_detected_by_report_summary():
    rules = MaterialRuleSet(
        material_id="fake-missing-reason",
        display_name="Fake Missing Reason",
        base_profile_hint="Generic PLA",
        process_overrides={
            "support_style": "snug",
        },
        categories={
            "process.support_style": "behavior",
        },
    )

    rows = material_delta_rows(
        {"support_style": "default"},
        rules,
        profile_scope="process",
    )

    assert rows[0]["reason"] == "reason not assigned"
    assert summarize_delta_rows(rows)["missing_reasons"] == 1
