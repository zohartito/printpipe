"""Conservative PC, PA, and PA-CF material rule foundations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PreflightNote:
    """One operator-facing preflight note for a material rule."""

    code: str
    severity: str
    category: str
    message: str


@dataclass(frozen=True)
class MaterialRule:
    """Foundation overrides and receipts metadata for one material family."""

    material: str
    family: str
    filament_overrides: Mapping[str, Any]
    process_overrides: Mapping[str, Any]
    setting_categories: Mapping[str, str]
    setting_reasons: Mapping[str, str]
    preflight_notes: tuple[PreflightNote, ...]

    def profile_overrides(self) -> dict[str, Any]:
        """Return merged filament and process overrides for settings deltas."""
        merged: dict[str, Any] = {}
        merged.update(copy.deepcopy(dict(self.filament_overrides)))
        merged.update(copy.deepcopy(dict(self.process_overrides)))
        return merged


def get_material_rule(material: str) -> MaterialRule:
    """Return the PC/PA foundation rule for a material name or alias."""
    key = _normalize_material_key(material)
    canonical = _ALIASES.get(key)
    if canonical is None:
        supported = ", ".join(sorted(_ALIASES))
        raise KeyError(f"unsupported PC/PA material {material!r}; supported aliases: {supported}")
    return _RULES[canonical]


def supported_materials() -> tuple[str, ...]:
    """Return the canonical material names covered by this foundation."""
    return tuple(_RULES)


_SETTING_CATEGORIES = {
    "filament_type": "material_identity",
    "nozzle_temperature": "temperature",
    "nozzle_temperature_initial_layer": "temperature",
    "filament_max_volumetric_speed": "throughput",
    "textured_plate_temp": "bed_adhesion",
    "textured_plate_temp_initial_layer": "bed_adhesion",
    "hot_plate_temp": "bed_adhesion",
    "hot_plate_temp_initial_layer": "bed_adhesion",
    "eng_plate_temp": "bed_adhesion",
    "eng_plate_temp_initial_layer": "bed_adhesion",
    "chamber_temperatures": "chamber_preheat",
    "fan_min_speed": "cooling",
    "fan_max_speed": "cooling",
    "overhang_fan_speed": "cooling",
    "slow_down_layer_time": "cooling",
    "fan_cooling_layer_time": "cooling",
    "brim_type": "bed_adhesion",
    "brim_width": "bed_adhesion",
    "brim_object_gap": "bed_adhesion",
    "wall_loops": "strength_shell",
    "top_shell_layers": "strength_shell",
    "bottom_shell_layers": "strength_shell",
    "sparse_infill_density": "strength_shell",
}


def _select_categories(*override_maps: Mapping[str, Any]) -> dict[str, str]:
    keys = set().union(*(overrides.keys() for overrides in override_maps))
    missing = sorted(keys - set(_SETTING_CATEGORIES))
    if missing:
        raise ValueError(f"PC/PA setting categories missing keys: {missing}")
    return {key: _SETTING_CATEGORIES[key] for key in keys}


_PC_FILAMENT_OVERRIDES = {
    "filament_type": ["PC"],
    "nozzle_temperature": ["280"],
    "nozzle_temperature_initial_layer": ["270"],
    "filament_max_volumetric_speed": ["8"],
    "textured_plate_temp": ["100"],
    "textured_plate_temp_initial_layer": ["100"],
    "hot_plate_temp": ["100"],
    "hot_plate_temp_initial_layer": ["100"],
    "eng_plate_temp": ["100"],
    "eng_plate_temp_initial_layer": ["100"],
    "chamber_temperatures": ["60"],
    "fan_min_speed": ["0"],
    "fan_max_speed": ["20"],
    "overhang_fan_speed": ["30"],
    "slow_down_layer_time": ["12"],
    "fan_cooling_layer_time": ["30"],
}

_PC_PROCESS_OVERRIDES = {
    "brim_type": "outer_only",
    "brim_width": "8",
    "brim_object_gap": "0.05",
    "wall_loops": "4",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "sparse_infill_density": "25%",
}

_PA_FILAMENT_OVERRIDES = {
    "filament_type": ["PA"],
    "nozzle_temperature": ["260"],
    "nozzle_temperature_initial_layer": ["260"],
    "filament_max_volumetric_speed": ["8"],
    "textured_plate_temp": ["90"],
    "textured_plate_temp_initial_layer": ["90"],
    "hot_plate_temp": ["90"],
    "hot_plate_temp_initial_layer": ["90"],
    "eng_plate_temp": ["90"],
    "eng_plate_temp_initial_layer": ["90"],
    "chamber_temperatures": ["45"],
    "fan_min_speed": ["10"],
    "fan_max_speed": ["35"],
    "overhang_fan_speed": ["50"],
    "slow_down_layer_time": ["10"],
    "fan_cooling_layer_time": ["30"],
}

_PA_PROCESS_OVERRIDES = {
    "brim_type": "outer_only",
    "brim_width": "8",
    "brim_object_gap": "0.05",
    "wall_loops": "4",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "sparse_infill_density": "25%",
}

_PA_CF_FILAMENT_OVERRIDES = {
    "filament_type": ["PA-CF"],
    "nozzle_temperature": ["285"],
    "nozzle_temperature_initial_layer": ["285"],
    "filament_max_volumetric_speed": ["6"],
    "textured_plate_temp": ["100"],
    "textured_plate_temp_initial_layer": ["100"],
    "hot_plate_temp": ["100"],
    "hot_plate_temp_initial_layer": ["100"],
    "eng_plate_temp": ["100"],
    "eng_plate_temp_initial_layer": ["100"],
    "chamber_temperatures": ["55"],
    "fan_min_speed": ["10"],
    "fan_max_speed": ["30"],
    "overhang_fan_speed": ["40"],
    "slow_down_layer_time": ["8"],
    "fan_cooling_layer_time": ["20"],
}

_PA_CF_PROCESS_OVERRIDES = {
    "brim_type": "outer_only",
    "brim_width": "10",
    "brim_object_gap": "0.05",
    "wall_loops": "4",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "sparse_infill_density": "30%",
}

_COMMON_PROCESS_REASONS = {
    "brim_type": "Use an outer brim as a conservative first-line warp guard.",
    "brim_width": "Increase brim contact area for engineering materials that can lift while cooling.",
    "brim_object_gap": "Keep a small brim gap so adhesion improves without intentionally welding the brim to the part.",
    "wall_loops": "Raise perimeter count for stronger shells and better heat-stress tolerance.",
    "top_shell_layers": "Raise top shell coverage for stronger closed surfaces.",
    "bottom_shell_layers": "Raise bottom shell coverage for stronger bed-facing surfaces.",
    "sparse_infill_density": "Use a moderate strength baseline before object-specific load analysis exists.",
}

_PC_REASONS = {
    **_COMMON_PROCESS_REASONS,
    "filament_type": "Mark the profile as PC for downstream selection and receipts.",
    "nozzle_temperature": "PC needs high melt temperature for inter-layer bonding.",
    "nozzle_temperature_initial_layer": "Use a slightly lower first-layer PC nozzle temperature to reduce initial ooze while staying hot enough to bond.",
    "filament_max_volumetric_speed": "Limit PC flow rate until printer, nozzle, and part geometry are slice-verified.",
    "textured_plate_temp": "Run a hot bed for PC adhesion and warp resistance.",
    "textured_plate_temp_initial_layer": "Keep the PC first layer on a hot bed to anchor corners.",
    "hot_plate_temp": "Run a hot bed for PC adhesion and warp resistance.",
    "hot_plate_temp_initial_layer": "Keep the PC first layer on a hot bed to anchor corners.",
    "eng_plate_temp": "Run a hot engineering plate for PC adhesion and warp resistance.",
    "eng_plate_temp_initial_layer": "Keep the PC first layer on a hot engineering plate to anchor corners.",
    "chamber_temperatures": "Use a warm enclosed chamber for PC to reduce thermal shock and layer splitting.",
    "fan_min_speed": "Minimize PC part cooling to preserve layer bonding.",
    "fan_max_speed": "Cap PC part cooling so overhang help does not create excessive shrink stress.",
    "overhang_fan_speed": "Allow only limited overhang cooling for PC.",
    "slow_down_layer_time": "Give small PC layers time without relying on high fan speed.",
    "fan_cooling_layer_time": "Delay stronger cooling response for PC because heat retention is usually preferable.",
}

_PA_REASONS = {
    **_COMMON_PROCESS_REASONS,
    "filament_type": "Mark the profile as PA for downstream selection and receipts.",
    "nozzle_temperature": "Use a nylon-safe melt temperature that favors bonding without assuming a specific PA blend.",
    "nozzle_temperature_initial_layer": "Keep PA first-layer melt temperature aligned with the print temperature for consistent adhesion.",
    "filament_max_volumetric_speed": "Limit PA flow rate because wet or borderline-dry nylon can lose strength quickly at high throughput.",
    "textured_plate_temp": "Use a warm bed for PA adhesion while leaving room for plate-specific tuning.",
    "textured_plate_temp_initial_layer": "Keep the PA first layer warm enough to resist corner lift.",
    "hot_plate_temp": "Use a warm bed for PA adhesion while leaving room for plate-specific tuning.",
    "hot_plate_temp_initial_layer": "Keep the PA first layer warm enough to resist corner lift.",
    "eng_plate_temp": "Use a warm engineering plate for PA adhesion while leaving room for adhesive tuning.",
    "eng_plate_temp_initial_layer": "Keep the PA first layer warm enough to resist corner lift on engineering plates.",
    "chamber_temperatures": "Use enclosure preheat for PA to reduce warp, especially on broad parts.",
    "fan_min_speed": "Keep baseline PA cooling low to protect layer bonding.",
    "fan_max_speed": "Cap PA cooling because excessive fan can weaken nylon parts and worsen warp.",
    "overhang_fan_speed": "Allow moderate overhang cooling for PA without making fan the default fix.",
    "slow_down_layer_time": "Slow small PA layers before adding more fan.",
    "fan_cooling_layer_time": "Delay aggressive PA cooling response to protect strength.",
}

_PA_CF_REASONS = {
    **_COMMON_PROCESS_REASONS,
    "filament_type": "Mark the profile as PA-CF for downstream selection and receipts.",
    "nozzle_temperature": "Use a hotter nylon-CF baseline for filled filament bonding.",
    "nozzle_temperature_initial_layer": "Keep PA-CF first-layer temperature hot to wet the bed and bond the filled filament.",
    "filament_max_volumetric_speed": "Limit PA-CF flow because filled nylon is more abrasive and less forgiving of pressure spikes.",
    "textured_plate_temp": "Use a hot bed for PA-CF adhesion and warp control.",
    "textured_plate_temp_initial_layer": "Keep the PA-CF first layer hot to anchor fiber-filled corners.",
    "hot_plate_temp": "Use a hot bed for PA-CF adhesion and warp control.",
    "hot_plate_temp_initial_layer": "Keep the PA-CF first layer hot to anchor fiber-filled corners.",
    "eng_plate_temp": "Use a hot engineering plate for PA-CF adhesion and warp control.",
    "eng_plate_temp_initial_layer": "Keep the PA-CF first layer hot to anchor fiber-filled corners on engineering plates.",
    "chamber_temperatures": "Use enclosure preheat for PA-CF to reduce warp and preserve layer bonding.",
    "fan_min_speed": "Keep PA-CF baseline cooling low for bonding.",
    "fan_max_speed": "Cap PA-CF cooling because filled nylon already gains stiffness and can warp if chilled.",
    "overhang_fan_speed": "Allow only moderate overhang cooling for PA-CF.",
    "slow_down_layer_time": "Slow small PA-CF layers before increasing fan.",
    "fan_cooling_layer_time": "Delay stronger PA-CF cooling response to protect strength.",
}

_RULES = {
    "PC": MaterialRule(
        material="PC",
        family="PC",
        filament_overrides=_PC_FILAMENT_OVERRIDES,
        process_overrides=_PC_PROCESS_OVERRIDES,
        setting_categories=_select_categories(_PC_FILAMENT_OVERRIDES, _PC_PROCESS_OVERRIDES),
        setting_reasons=_PC_REASONS,
        preflight_notes=(
            PreflightNote(
                code="pc_dry_before_print",
                severity="warning",
                category="drying",
                message="Dry PC before printing and keep the spool covered; wet PC causes bubbles, haze, and weak layers.",
            ),
            PreflightNote(
                code="pc_enclosure_preheat",
                severity="warning",
                category="chamber_preheat",
                message="Use an enclosed printer and preheat the chamber and bed until temperatures stabilize before starting PC.",
            ),
            PreflightNote(
                code="pc_bed_adhesion",
                severity="warning",
                category="bed_adhesion",
                message="Use a PC-compatible plate or adhesive and confirm the brim plan before printing broad PC parts.",
            ),
        ),
    ),
    "PA": MaterialRule(
        material="PA",
        family="PA",
        filament_overrides=_PA_FILAMENT_OVERRIDES,
        process_overrides=_PA_PROCESS_OVERRIDES,
        setting_categories=_select_categories(_PA_FILAMENT_OVERRIDES, _PA_PROCESS_OVERRIDES),
        setting_reasons=_PA_REASONS,
        preflight_notes=(
            PreflightNote(
                code="pa_moisture_hard_gate",
                severity="hard_gate",
                category="drying",
                message="Moisture is a hard gate for PA: dry filament immediately before printing and do not start if popping, steam, or surface fuzz appears.",
            ),
            PreflightNote(
                code="pa_dry_box",
                severity="warning",
                category="drying",
                message="Feed PA from a dry box during the run because nylon reabsorbs moisture quickly.",
            ),
            PreflightNote(
                code="pa_enclosure_preheat",
                severity="warning",
                category="chamber_preheat",
                message="Use an enclosure and preheat the chamber and bed before printing PA parts with broad footprints.",
            ),
        ),
    ),
    "PA-CF": MaterialRule(
        material="PA-CF",
        family="PA",
        filament_overrides=_PA_CF_FILAMENT_OVERRIDES,
        process_overrides=_PA_CF_PROCESS_OVERRIDES,
        setting_categories=_select_categories(_PA_CF_FILAMENT_OVERRIDES, _PA_CF_PROCESS_OVERRIDES),
        setting_reasons=_PA_CF_REASONS,
        preflight_notes=(
            PreflightNote(
                code="pa_cf_moisture_hard_gate",
                severity="hard_gate",
                category="drying",
                message="Moisture is a hard gate for PA-CF: dry filament immediately before printing and do not start if popping, steam, or rough matte extrusion appears.",
            ),
            PreflightNote(
                code="pa_cf_hardened_nozzle",
                severity="hard_gate",
                category="hardware",
                message="Use a hardened nozzle for PA-CF; carbon fiber is abrasive and can damage soft brass nozzles.",
            ),
            PreflightNote(
                code="pa_cf_enclosure_preheat",
                severity="warning",
                category="chamber_preheat",
                message="Use enclosure preheat and a hot bed for PA-CF so stiff fiber-filled corners stay anchored.",
            ),
        ),
    ),
}

_ALIASES = {
    "pc": "PC",
    "polycarbonate": "PC",
    "pa": "PA",
    "polyamide": "PA",
    "nylon": "PA",
    "pa-cf": "PA-CF",
    "pacf": "PA-CF",
    "polyamide-cf": "PA-CF",
    "nylon-cf": "PA-CF",
    "nyloncf": "PA-CF",
    "carbon-fiber-nylon": "PA-CF",
}


def _normalize_material_key(material: str) -> str:
    text = material.strip().lower().replace("_", "-").replace("/", "-")
    return "-".join(text.split())


def _validate_rules() -> None:
    for rule in _RULES.values():
        override_keys = set(rule.profile_overrides())
        missing_categories = sorted(override_keys - set(rule.setting_categories))
        missing_reasons = sorted(override_keys - set(rule.setting_reasons))
        if missing_categories:
            raise ValueError(f"{rule.material} categories missing keys: {missing_categories}")
        if missing_reasons:
            raise ValueError(f"{rule.material} reasons missing keys: {missing_reasons}")


_validate_rules()

__all__ = [
    "MaterialRule",
    "PreflightNote",
    "get_material_rule",
    "supported_materials",
]
