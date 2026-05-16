from __future__ import annotations

from printpipe.web.options import (
    default_selector_values,
    material_options,
    printer_options,
    selector_catalog,
)


def test_printer_options_expose_launch_p2s_target():
    printers = printer_options()

    assert len(printers) == 1
    launch_printer = printers[0]

    assert launch_printer["id"] == "bambu-p2s-0-4-nozzle"
    assert launch_printer["label"] == "Bambu Lab P2S (0.4 mm nozzle)"
    assert launch_printer["printer_settings_id"] == "Bambu Lab P2S 0.4 nozzle"
    assert launch_printer["printer_model"] == "Bambu Lab P2S"
    assert launch_printer["is_launch_default"] is True
    assert launch_printer["preflight_hints"]
    assert any("Bambu Studio" in hint for hint in launch_printer["preflight_hints"])


def test_material_options_cover_wave6_selectable_materials_with_ui_copy():
    materials = material_options()

    assert [option["id"] for option in materials] == [
        "pla",
        "pla-plus",
        "petg-foundation",
        "tpu-90a-foundation",
        "tpu-95a-foundation",
        "sunlu-tpu-90a-slipper",
        "abs",
        "asa",
        "pc",
        "pa",
        "pa-cf",
    ]
    assert {option["family"] for option in materials} == {
        "PLA",
        "PETG",
        "TPU",
        "ABS/ASA",
        "PC",
        "PA",
    }
    assert all(option["label"].strip() for option in materials)
    assert all(option["description"].strip() for option in materials)
    assert all(option["base_profile_hint"].strip() for option in materials)
    assert all(option["validation_status"] == "software-foundation/unvalidated" for option in materials)
    assert all(option["preflight_hints"] for option in materials)
    assert any(option["is_launch_default"] for option in materials)


def test_default_selector_values_point_to_available_options():
    defaults = default_selector_values()

    printer_ids = {option["id"] for option in printer_options()}
    material_ids = {option["id"] for option in material_options()}

    assert defaults == {
        "printer_id": "bambu-p2s-0-4-nozzle",
        "material_id": "sunlu-tpu-90a-slipper",
    }
    assert defaults["printer_id"] in printer_ids
    assert defaults["material_id"] in material_ids


def test_selector_catalog_bundles_copy_safe_options_and_defaults():
    first = selector_catalog()
    second = selector_catalog()

    first["printers"][0]["preflight_hints"].append("mutated")
    first["materials"][0]["preflight_hints"].append("mutated")
    first["defaults"]["material_id"] = "mutated"

    assert "mutated" not in second["printers"][0]["preflight_hints"]
    assert "mutated" not in second["materials"][0]["preflight_hints"]
    assert second["defaults"]["material_id"] == "sunlu-tpu-90a-slipper"
