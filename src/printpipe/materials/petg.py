"""Conservative PETG material rule foundation."""

from __future__ import annotations

import copy
from typing import Any

from .core import MaterialRuleSet

_VALIDATION_STATUS = "defaults-derived/unvalidated"
_DEFAULTS_NOTE = "Defaults-derived/unvalidated"

_PROFILE_INTENT = (
    "Clone a Generic PETG or Bambu PETG Basic baseline when available, then apply "
    "conservative PETG family overrides for adhesion, cooling, volumetric flow, "
    "and stringing control."
)

_SOURCE_NOTES = (
    "Derived from installed Bambu Studio PETG defaults: Generic PETG @base, "
    "Generic PETG @BBL P2S, Bambu PETG Basic @base, and Bambu PETG Basic @BBL P2S 0.4 nozzle.",
    "Process speed and travel caps are conservative foundations relative to the P2S standard "
    "process and must be slice-tested before being treated as product-tuned PETG rules.",
)

_PREFLIGHT_NOTES = (
    "Dry PETG before important prints; wet PETG tends to string and pop even when slicer settings are conservative.",
    "Clean the textured PEI plate and avoid aggressive first-layer squish because PETG can bond strongly to PEI.",
)

_FILAMENT_OVERRIDES: dict[str, Any] = {
    "filament_type": ["PETG"],
    "filament_vendor": ["Generic"],
    "filament_flow_ratio": ["0.95"],
    "nozzle_temperature_initial_layer": ["245"],
    "nozzle_temperature": ["250"],
    "textured_plate_temp_initial_layer": ["70"],
    "textured_plate_temp": ["70"],
    "hot_plate_temp_initial_layer": ["70"],
    "hot_plate_temp": ["70"],
    "first_x_layer_fan_speed": ["0"],
    "fan_min_speed": ["30"],
    "fan_max_speed": ["60"],
    "overhang_fan_speed": ["50"],
    "fan_cooling_layer_time": ["30"],
    "slow_down_layer_time": ["12"],
    "filament_max_volumetric_speed": ["8"],
    "filament_retraction_length": ["0.4"],
    "filament_z_hop_types": ["Spiral Lift"],
    "filament_wipe": ["1"],
    "filament_wipe_distance": ["1"],
}

_PROCESS_OVERRIDES: dict[str, Any] = {
    "curr_bed_type": "Textured PEI Plate",
    "brim_width": "5",
    "brim_object_gap": "0.1",
    "initial_layer_speed": ["30"],
    "initial_layer_infill_speed": ["60"],
    "outer_wall_speed": ["100"],
    "inner_wall_speed": ["150"],
    "sparse_infill_speed": ["150"],
    "internal_solid_infill_speed": ["120"],
    "top_surface_speed": ["80"],
    "travel_speed": ["300"],
    "reduce_crossing_wall": "1",
    "max_travel_detour_distance": "80",
}

_REASONS = {
    "filament_type": "Declare PETG as the material family for Bambu-compatible profile selection.",
    "filament_vendor": "Use a neutral vendor label because brand-specific PETG tuning is not validated.",
    "filament_flow_ratio": (
        f"{_DEFAULTS_NOTE}: keep the 0.95 PETG flow-ratio baseline seen in Bambu PETG defaults."
    ),
    "nozzle_temperature_initial_layer": (
        f"{_DEFAULTS_NOTE}: start near Bambu PETG Basic's 245 C first-layer temperature."
    ),
    "nozzle_temperature": (
        f"{_DEFAULTS_NOTE}: use a moderate 250 C PETG print temperature rather than an aggressive high-flow value."
    ),
    "textured_plate_temp_initial_layer": (
        f"{_DEFAULTS_NOTE}: use the 70 C textured PEI first-layer bed target from Bambu PETG defaults."
    ),
    "textured_plate_temp": (
        f"{_DEFAULTS_NOTE}: keep the 70 C textured PEI bed target after layer one for PETG adhesion."
    ),
    "hot_plate_temp_initial_layer": (
        f"{_DEFAULTS_NOTE}: mirror the PETG 70 C first-layer bed target for hot plate profiles."
    ),
    "hot_plate_temp": (
        f"{_DEFAULTS_NOTE}: mirror the PETG 70 C bed target for hot plate profiles."
    ),
    "first_x_layer_fan_speed": (
        f"{_DEFAULTS_NOTE}: keep fan off on the first layer to protect PETG bed adhesion."
    ),
    "fan_min_speed": (
        f"{_DEFAULTS_NOTE}: use Bambu PETG Basic's restrained 30 percent minimum fan on P2S."
    ),
    "fan_max_speed": (
        f"{_DEFAULTS_NOTE}: cap part cooling at 60 percent until PrintPipe has PETG dogfood evidence."
    ),
    "overhang_fan_speed": (
        f"{_DEFAULTS_NOTE}: allow a moderate 50 percent overhang fan cap from Bambu PETG Basic P2S."
    ),
    "fan_cooling_layer_time": (
        f"{_DEFAULTS_NOTE}: retain the 30 s PETG cooling-layer-time baseline from Bambu defaults."
    ),
    "slow_down_layer_time": (
        f"{_DEFAULTS_NOTE}: retain the 12 s PETG slowdown trigger instead of assuming high-flow cooling."
    ),
    "filament_max_volumetric_speed": (
        f"{_DEFAULTS_NOTE}: use the conservative 8 mm3/s Bambu PETG Basic base MVS until calibrated."
    ),
    "filament_retraction_length": (
        f"{_DEFAULTS_NOTE}: use the PETG Basic P2S 0.4 mm retract length for stringing control."
    ),
    "filament_z_hop_types": (
        f"{_DEFAULTS_NOTE}: preserve the PETG Basic P2S Spiral Lift hop style for wipe/retract moves."
    ),
    "filament_wipe": (
        f"{_DEFAULTS_NOTE}: enable the PETG Basic P2S wipe behavior to reduce nozzle ooze."
    ),
    "filament_wipe_distance": (
        f"{_DEFAULTS_NOTE}: use the PETG Basic P2S 1 mm wipe distance as a cautious starting point."
    ),
    "curr_bed_type": (
        f"{_DEFAULTS_NOTE}: select Textured PEI so Bambu validation does not default PETG jobs to Cool Plate."
    ),
    "brim_width": (
        f"{_DEFAULTS_NOTE}: keep the common 5 mm brim foundation for PETG adhesion-sensitive jobs."
    ),
    "brim_object_gap": (
        f"{_DEFAULTS_NOTE}: keep a 0.1 mm brim gap so PETG adhesion help remains removable."
    ),
    "initial_layer_speed": (
        f"{_DEFAULTS_NOTE}: limit first-layer speed below the P2S standard process to improve PETG adhesion."
    ),
    "initial_layer_infill_speed": (
        f"{_DEFAULTS_NOTE}: keep first-layer infill slower than the P2S standard process for PETG."
    ),
    "outer_wall_speed": (
        f"{_DEFAULTS_NOTE}: cap PETG outer walls below fast P2S defaults while MVS remains uncalibrated."
    ),
    "inner_wall_speed": (
        f"{_DEFAULTS_NOTE}: cap PETG inner walls below fast P2S defaults while MVS remains uncalibrated."
    ),
    "sparse_infill_speed": (
        f"{_DEFAULTS_NOTE}: cap sparse infill so the 8 mm3/s MVS remains the primary limiter."
    ),
    "internal_solid_infill_speed": (
        f"{_DEFAULTS_NOTE}: cap internal solid infill below fast P2S defaults for PETG reliability."
    ),
    "top_surface_speed": (
        f"{_DEFAULTS_NOTE}: keep PETG top surfaces slower than fast P2S defaults to reduce dragging and gloss defects."
    ),
    "travel_speed": (
        f"{_DEFAULTS_NOTE}: keep travel speed below fast P2S defaults while PETG stringing rules are unvalidated."
    ),
    "reduce_crossing_wall": (
        f"{_DEFAULTS_NOTE}: avoid crossing walls as a foundation-level PETG stringing mitigation."
    ),
    "max_travel_detour_distance": (
        f"{_DEFAULTS_NOTE}: allow moderate detours so avoid-crossing-walls can reduce PETG travel strings."
    ),
}

_CATEGORIES = {
    "filament_type": "metadata",
    "filament_vendor": "metadata",
    "filament_flow_ratio": "temperature_flow",
    "nozzle_temperature_initial_layer": "temperature_flow",
    "nozzle_temperature": "temperature_flow",
    "textured_plate_temp_initial_layer": "bed_adhesion",
    "textured_plate_temp": "bed_adhesion",
    "hot_plate_temp_initial_layer": "bed_adhesion",
    "hot_plate_temp": "bed_adhesion",
    "first_x_layer_fan_speed": "bed_adhesion",
    "fan_min_speed": "cooling",
    "fan_max_speed": "cooling",
    "overhang_fan_speed": "cooling",
    "fan_cooling_layer_time": "cooling",
    "slow_down_layer_time": "cooling",
    "filament_max_volumetric_speed": "mvs_speed",
    "filament_retraction_length": "stringing_retraction",
    "filament_z_hop_types": "stringing_retraction",
    "filament_wipe": "stringing_retraction",
    "filament_wipe_distance": "stringing_retraction",
    "curr_bed_type": "bed_adhesion",
    "brim_width": "bed_adhesion",
    "brim_object_gap": "bed_adhesion",
    "initial_layer_speed": "bed_adhesion",
    "initial_layer_infill_speed": "bed_adhesion",
    "outer_wall_speed": "mvs_speed",
    "inner_wall_speed": "mvs_speed",
    "sparse_infill_speed": "mvs_speed",
    "internal_solid_infill_speed": "mvs_speed",
    "top_surface_speed": "mvs_speed",
    "travel_speed": "mvs_speed",
    "reduce_crossing_wall": "stringing_retraction",
    "max_travel_detour_distance": "stringing_retraction",
}

PETG_RULES: dict[str, MaterialRuleSet] = {
    "petg-foundation": MaterialRuleSet(
        material_id="petg-foundation",
        display_name="PETG Foundation",
        base_profile_hint="Generic PETG @BBL P2S",
        filament_overrides=_FILAMENT_OVERRIDES,
        process_overrides=_PROCESS_OVERRIDES,
        reasons=_REASONS,
        categories=_CATEGORIES,
        preflight_notes=_PREFLIGHT_NOTES,
    ),
}

_ALIASES = {
    "petg": "petg-foundation",
    "generic_petg": "petg-foundation",
    "petg_foundation": "petg-foundation",
    "petg-foundation": "petg-foundation",
}


def available_petg_rules() -> dict[str, MaterialRuleSet]:
    """Return PETG rule-set catalog entries keyed by stable id."""
    return dict(PETG_RULES)


def get_petg_rule(rule_id: str = "petg") -> MaterialRuleSet:
    """Return one PETG rule-set catalog entry."""
    normalized = _normalize_rule_id(rule_id)
    return PETG_RULES[normalized]


def build_petg_overrides(rule_id: str = "petg") -> dict[str, Any]:
    """Return copy-safe PETG overrides plus receipt categories and reasons."""
    rule = get_petg_rule(rule_id)
    return {
        "material_id": rule.material_id,
        "display_name": rule.display_name,
        "base_profile_hint": rule.base_profile_hint,
        "profile_intent": _PROFILE_INTENT,
        "validation_status": _VALIDATION_STATUS,
        "filament_overrides": copy.deepcopy(dict(rule.filament_overrides)),
        "process_overrides": copy.deepcopy(dict(rule.process_overrides)),
        "reasons": dict(rule.reasons),
        "categories": dict(rule.categories),
        "preflight_notes": tuple(rule.preflight_notes),
        "source_notes": _SOURCE_NOTES,
    }


def _normalize_rule_id(rule_id: str) -> str:
    normalized = rule_id.strip().lower().replace(" ", "_")
    if normalized in _ALIASES:
        return _ALIASES[normalized]
    supported = ", ".join(sorted(PETG_RULES))
    raise ValueError(f"unsupported PETG rule {rule_id!r}; supported rules: {supported}")
