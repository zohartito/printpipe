"""Conservative ABS/ASA material rule foundations."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PreflightNote:
    """Operator-facing material guidance that is not always a slicer key."""

    category: str
    message: str


@dataclass(frozen=True)
class MaterialRule:
    """Filament/process overrides plus receipt metadata for one material variant."""

    family: str
    variant: str
    filament_overrides: Mapping[str, Any]
    process_overrides: Mapping[str, Any]
    categories: Mapping[str, str]
    reasons: Mapping[str, str]
    preflight_notes: tuple[PreflightNote, ...]

    def combined_overrides(self) -> dict[str, Any]:
        """Return a copy of all slicer-facing overrides for delta reporting."""
        combined: dict[str, Any] = {}
        for overrides in (self.filament_overrides, self.process_overrides):
            for key, value in overrides.items():
                combined[key] = copy.deepcopy(value)
        return combined

    def override_keys(self) -> tuple[str, ...]:
        """Return stable override keys across filament and process scopes."""
        return tuple(self.combined_overrides())


FAMILY = "ABS/ASA"

COMMON_FILAMENT_CATEGORIES = {
    "filament_type": "metadata",
    "nozzle_temperature": "temperature",
    "nozzle_temperature_initial_layer": "temperature",
    "hot_plate_temp": "bed_adhesion",
    "hot_plate_temp_initial_layer": "bed_adhesion",
    "textured_plate_temp": "bed_adhesion",
    "textured_plate_temp_initial_layer": "bed_adhesion",
    "eng_plate_temp": "bed_adhesion",
    "eng_plate_temp_initial_layer": "bed_adhesion",
    "chamber_temperatures": "chamber",
    "filament_max_volumetric_speed": "flow",
    "fan_min_speed": "cooling",
    "fan_max_speed": "cooling",
    "slow_down_layer_time": "cooling",
}

COMMON_PROCESS_OVERRIDES = {
    "brim_type": "outer_only",
    "brim_width": "8",
    "brim_object_gap": "0.1",
}

COMMON_PROCESS_CATEGORIES = {
    "brim_type": "brim",
    "brim_width": "brim",
    "brim_object_gap": "brim",
}

COMMON_PROCESS_REASONS = {
    "brim_type": "Use an outer brim to add edge hold without filling internal holes.",
    "brim_width": "ABS and ASA shrink as they cool, so a wider brim gives corners more bed contact.",
    "brim_object_gap": "Keep a small removable gap instead of welding the brim to the part.",
}

ABS_FILAMENT_OVERRIDES = {
    "filament_type": ["ABS"],
    "nozzle_temperature": ["260"],
    "nozzle_temperature_initial_layer": ["260"],
    "hot_plate_temp": ["100"],
    "hot_plate_temp_initial_layer": ["100"],
    "textured_plate_temp": ["100"],
    "textured_plate_temp_initial_layer": ["100"],
    "eng_plate_temp": ["100"],
    "eng_plate_temp_initial_layer": ["100"],
    "chamber_temperatures": ["60"],
    "filament_max_volumetric_speed": ["10"],
    "fan_min_speed": ["0"],
    "fan_max_speed": ["35"],
    "slow_down_layer_time": ["12"],
}

ABS_FILAMENT_REASONS = {
    "filament_type": "Tag the override as ABS so downstream receipts can group it correctly.",
    "nozzle_temperature": "Use a moderate ABS nozzle temperature as a conservative generic starting point.",
    "nozzle_temperature_initial_layer": "Keep the first layer hot enough for adhesion without exceeding generic ABS assumptions.",
    "hot_plate_temp": "Raise smooth high-temperature plate targets to reduce ABS corner lift.",
    "hot_plate_temp_initial_layer": "Start ABS on a hot bed so the first layer bonds before enclosure heat stabilizes.",
    "textured_plate_temp": "Raise textured plate targets to favor ABS adhesion on warp-prone parts.",
    "textured_plate_temp_initial_layer": "Use the same hot first-layer textured plate target for consistent edge hold.",
    "eng_plate_temp": "Raise engineering plate targets to support ABS adhesion when that plate is selected.",
    "eng_plate_temp_initial_layer": "Start ABS on a hot engineering plate for stronger first-layer anchoring.",
    "chamber_temperatures": "Bambu profiles expose chamber_temperatures; 60 C records the enclosure target when supported.",
    "filament_max_volumetric_speed": "Limit generic ABS flow until brand-specific melt flow is known.",
    "fan_min_speed": "Minimize part cooling for ABS to preserve layer bonding and reduce thermal shock.",
    "fan_max_speed": "Cap ABS fan speed well below PLA-style cooling to reduce curling.",
    "slow_down_layer_time": "Give small ABS layers time to cool without forcing aggressive fan cooling.",
}

ASA_FILAMENT_OVERRIDES = {
    "filament_type": ["ASA"],
    "nozzle_temperature": ["255"],
    "nozzle_temperature_initial_layer": ["260"],
    "hot_plate_temp": ["100"],
    "hot_plate_temp_initial_layer": ["100"],
    "textured_plate_temp": ["100"],
    "textured_plate_temp_initial_layer": ["100"],
    "eng_plate_temp": ["100"],
    "eng_plate_temp_initial_layer": ["100"],
    "chamber_temperatures": ["60"],
    "filament_max_volumetric_speed": ["8"],
    "fan_min_speed": ["0"],
    "fan_max_speed": ["25"],
    "slow_down_layer_time": ["12"],
}

ASA_FILAMENT_REASONS = {
    "filament_type": "Tag the override as ASA so downstream receipts can group it correctly.",
    "nozzle_temperature": "Use a slightly cooler ASA steady-state nozzle target than ABS to reduce overheating risk.",
    "nozzle_temperature_initial_layer": "Keep ASA's first layer warm for adhesion before settling to the print temperature.",
    "hot_plate_temp": "Use a high bed target to counter ASA shrink and edge lift.",
    "hot_plate_temp_initial_layer": "Start ASA on a hot bed so the first layer anchors before the chamber stabilizes.",
    "textured_plate_temp": "Raise textured plate targets to support ASA adhesion on larger footprints.",
    "textured_plate_temp_initial_layer": "Use the same hot first-layer textured plate target for consistent edge hold.",
    "eng_plate_temp": "Raise engineering plate targets to support ASA adhesion when that plate is selected.",
    "eng_plate_temp_initial_layer": "Start ASA on a hot engineering plate for stronger first-layer anchoring.",
    "chamber_temperatures": "Bambu profiles expose chamber_temperatures; 60 C records the enclosure target when supported.",
    "filament_max_volumetric_speed": "Limit generic ASA flow more than ABS until brand-specific flow data is known.",
    "fan_min_speed": "Minimize part cooling for ASA to reduce thermal gradients.",
    "fan_max_speed": "Cap ASA cooling lower than ABS because ASA commonly benefits from a steadier warm environment.",
    "slow_down_layer_time": "Give small ASA layers time to cool without relying on high fan speed.",
}

COMMON_PREFLIGHT_NOTES = (
    PreflightNote(
        "chamber",
        "Use an enclosed printer and let the chamber/air volume warm up before judging first-layer stability.",
    ),
    PreflightNote(
        "ventilation",
        "Run ABS/ASA with appropriate room ventilation or filtration; this is operator guidance, not a slicer override.",
    ),
    PreflightNote(
        "warping",
        "Avoid drafts, cold plates, and large sharp corners; split or reorient very large flat parts when possible.",
    ),
    PreflightNote(
        "preheat",
        "Preheat the bed and enclosure before starting larger jobs so the first layers do not see a cold chamber.",
    ),
)


def abs_rule() -> MaterialRule:
    """Return the conservative ABS rule foundation."""
    return _material_rule(
        variant="ABS",
        filament_overrides=ABS_FILAMENT_OVERRIDES,
        filament_reasons=ABS_FILAMENT_REASONS,
    )


def asa_rule() -> MaterialRule:
    """Return the conservative ASA rule foundation."""
    return _material_rule(
        variant="ASA",
        filament_overrides=ASA_FILAMENT_OVERRIDES,
        filament_reasons=ASA_FILAMENT_REASONS,
    )


def get_abs_asa_rule(variant: str) -> MaterialRule:
    """Return an ABS/ASA rule by material variant name."""
    normalized = variant.strip().upper()
    if normalized == "ABS":
        return abs_rule()
    if normalized == "ASA":
        return asa_rule()
    raise ValueError(f"unknown ABS/ASA material variant: {variant}")


def _material_rule(
    *,
    variant: str,
    filament_overrides: Mapping[str, Any],
    filament_reasons: Mapping[str, str],
) -> MaterialRule:
    categories = {
        **COMMON_FILAMENT_CATEGORIES,
        **COMMON_PROCESS_CATEGORIES,
    }
    reasons = {
        **filament_reasons,
        **COMMON_PROCESS_REASONS,
    }
    return MaterialRule(
        family=FAMILY,
        variant=variant,
        filament_overrides=copy.deepcopy(dict(filament_overrides)),
        process_overrides=copy.deepcopy(COMMON_PROCESS_OVERRIDES),
        categories=categories,
        reasons=reasons,
        preflight_notes=COMMON_PREFLIGHT_NOTES,
    )
