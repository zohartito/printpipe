"""TPU material rule foundations for Bambu profile overlays."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

SettingOverrides = dict[str, list[str]]
ReasonMap = dict[str, str]
CategoryMap = dict[str, str]


@dataclass(frozen=True)
class TpuMaterialRule:
    """Material-family overrides plus reporting metadata."""

    slug: str
    name: str
    family: str
    shore_hardness: str
    filament_overrides: SettingOverrides
    process_overrides: SettingOverrides
    hardware_notes: tuple[str, ...]
    preflight_notes: tuple[str, ...]
    reasons: ReasonMap
    categories: CategoryMap

    def combined_overrides(self) -> SettingOverrides:
        """Return filament and process overrides as one settings map for receipts."""
        merged = _copy_overrides(self.filament_overrides)
        for key, value in self.process_overrides.items():
            if key in merged:
                raise ValueError(f"duplicate override key across scopes: {key}")
            merged[key] = list(value)
        return merged

    def delta_metadata(self) -> dict[str, dict[str, str]]:
        """Return metadata kwargs for `generate_settings_delta_rows`."""
        return {
            "categories": dict(self.categories),
            "reasons": dict(self.reasons),
        }


def _build_rule(
    *,
    slug: str,
    name: str,
    shore_hardness: str,
    filament_overrides: SettingOverrides,
    process_overrides: SettingOverrides,
    hardware_notes: tuple[str, ...],
    preflight_notes: tuple[str, ...],
    reasons: ReasonMap,
    categories: CategoryMap,
) -> TpuMaterialRule:
    override_keys = set(filament_overrides) | set(process_overrides)
    missing_reasons = sorted(override_keys - set(reasons))
    if missing_reasons:
        raise ValueError(f"{slug} is missing reasons for: {', '.join(missing_reasons)}")

    complete_categories = {key: "behavior" for key in override_keys}
    complete_categories.update(categories)

    return TpuMaterialRule(
        slug=slug,
        name=name,
        family="TPU",
        shore_hardness=shore_hardness,
        filament_overrides=_copy_overrides(filament_overrides),
        process_overrides=_copy_overrides(process_overrides),
        hardware_notes=hardware_notes,
        preflight_notes=preflight_notes,
        reasons={key: reasons[key] for key in override_keys},
        categories={key: complete_categories[key] for key in override_keys},
    )


def _merge_overrides(*maps: SettingOverrides) -> SettingOverrides:
    merged: SettingOverrides = {}
    for source in maps:
        for key, value in source.items():
            merged[key] = list(value)
    return merged


def _merge_text(*maps: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for source in maps:
        merged.update(source)
    return merged


def _copy_overrides(overrides: SettingOverrides) -> SettingOverrides:
    return {key: list(value) for key, value in overrides.items()}


TPU_90A_FILAMENT_OVERRIDES: SettingOverrides = {
    "filament_type": ["TPU"],
    "filament_max_volumetric_speed": ["3.0"],
    "filament_retraction_length": ["1.0"],
    "filament_retraction_speed": ["30"],
    "filament_deretraction_speed": ["30"],
    "filament_z_hop": ["0.4"],
    "filament_z_hop_types": ["Normal Lift"],
    "filament_wipe": ["0"],
    "enable_pressure_advance": ["1"],
    "pressure_advance": ["0.040"],
    "fan_min_speed": ["30"],
    "fan_max_speed": ["60"],
    "close_fan_the_first_x_layers": ["1"],
    "slow_down_layer_time": ["8"],
    "slow_down_min_speed": ["15"],
    "additional_cooling_fan_speed": ["20"],
    "overhang_fan_threshold": ["50%"],
    "overhang_fan_speed": ["100"],
}

TPU_90A_PROCESS_OVERRIDES: SettingOverrides = {
    "outer_wall_speed": ["25"],
    "inner_wall_speed": ["40"],
    "small_perimeter_speed": ["20"],
    "sparse_infill_speed": ["50"],
    "internal_solid_infill_speed": ["45"],
    "top_surface_speed": ["20"],
    "gap_infill_speed": ["25"],
    "bridge_speed": ["20"],
    "initial_layer_speed": ["20"],
    "initial_layer_infill_speed": ["30"],
    "travel_speed": ["250"],
    "initial_layer_travel_speed": ["100"],
    "default_acceleration": ["3000"],
    "outer_wall_acceleration": ["2000"],
    "inner_wall_acceleration": ["3000"],
    "sparse_infill_acceleration": ["4000"],
    "travel_acceleration": ["6000"],
    "initial_layer_acceleration": ["500"],
    "top_surface_acceleration": ["2000"],
    "enable_overhang_speed": ["1"],
    "slow_down_for_layer_cooling": ["1"],
    "smooth_speed_discontinuity_area": ["1"],
    "support_type": ["normal(auto)"],
    "support_style": ["snug"],
    "support_top_z_distance": ["0.30"],
    "support_bottom_z_distance": ["0.30"],
    "support_interface_top_layers": ["0"],
    "support_interface_bottom_layers": ["0"],
    "support_interface_speed": ["30"],
    "support_interface_filament_flow": ["0.85"],
    "support_on_build_plate_only": ["1"],
    "brim_type": ["outer_only"],
    "brim_width": ["5"],
    "brim_object_gap": ["0.12"],
    "raft_layers": ["0"],
    "reduce_crossing_wall": ["1"],
}

TPU_90A_REASONS: ReasonMap = {
    "filament_type": "Marks the profile as TPU so downstream reports group it with flexible-material rules.",
    "filament_max_volumetric_speed": "Soft 90A TPU needs a conservative volumetric ceiling before MVS calibration.",
    "filament_retraction_length": "Short retraction limits stretch and blob formation in soft TPU.",
    "filament_retraction_speed": "30 mm/s avoids shearing or stretching the flexible strand.",
    "filament_deretraction_speed": "Matching deretraction keeps pressure recovery predictable after travel.",
    "filament_z_hop": "0.4 mm lift reduces nozzle drag across tacky flexible layers.",
    "filament_z_hop_types": "Normal Lift preserves the slipper-tested z-hop behavior.",
    "filament_wipe": "Disabling wipe avoids tearing or smearing soft TPU surfaces.",
    "enable_pressure_advance": "Manual pressure advance is retained while TPU auto flow dynamics calibration is avoided.",
    "pressure_advance": "Manual K = 0.040 preserves the known-good soft-TPU pressure advance baseline.",
    "fan_min_speed": "Lower body cooling supports layer fusion in flexible TPU.",
    "fan_max_speed": "Capping body fan at 60% avoids over-cooling and delamination.",
    "close_fan_the_first_x_layers": "Layer 1 keeps cooling off for PEI adhesion.",
    "slow_down_layer_time": "Small layers slow down so soft extrudate has time to set.",
    "slow_down_min_speed": "15 mm/s is the filament-side floor for cooling-driven slowdowns.",
    "additional_cooling_fan_speed": "Keeps the auxiliary fan low because strong side cooling weakens TPU bonds.",
    "overhang_fan_threshold": "Only overhang-heavy regions should receive aggressive cooling.",
    "overhang_fan_speed": "High overhang fan is reserved for droop-prone spans, not normal wall bonding.",
    "outer_wall_speed": "25 mm/s keeps 90A TPU walls smooth and within the flow ceiling.",
    "inner_wall_speed": "Hidden walls can run faster while remaining slower than rigid-filament defaults.",
    "small_perimeter_speed": "Small perimeter speed is reduced to limit pressure overshoot on tight curves.",
    "sparse_infill_speed": "Sparse infill stays below the practical soft-TPU flow ceiling.",
    "internal_solid_infill_speed": "Internal solid infill is slowed for continuous, reliable extrusion.",
    "top_surface_speed": "Top surfaces slow down to reduce TPU smearing.",
    "gap_infill_speed": "Gap infill matches pressure-sensitive outer wall behavior.",
    "bridge_speed": "Slow bridges reduce sag and give TPU strands time to land cleanly.",
    "initial_layer_speed": "Slow first layers prioritize adhesion over speed.",
    "initial_layer_infill_speed": "Initial infill remains conservative for bed bonding.",
    "travel_speed": "Travel is fast enough to limit ooze without relying on aggressive retraction.",
    "initial_layer_travel_speed": "Slower first-layer travel avoids disturbing brim and skirt adhesion.",
    "default_acceleration": "Reduced acceleration limits ringing and flow shocks with flexible filament.",
    "outer_wall_acceleration": "Outer walls use lower acceleration for smoother visible TPU surfaces.",
    "inner_wall_acceleration": "Inner walls keep a moderate acceleration because they are less cosmetic.",
    "sparse_infill_acceleration": "Continuous infill can tolerate the highest TPU acceleration in this rule.",
    "travel_acceleration": "Travel acceleration remains higher because it is toolhead motion, not extrusion flow.",
    "initial_layer_acceleration": "Low initial-layer acceleration protects bed adhesion.",
    "top_surface_acceleration": "Top surfaces match outer-wall acceleration for a cleaner finish.",
    "enable_overhang_speed": "Overhang slowdown is enabled because TPU droops easily.",
    "slow_down_for_layer_cooling": "Layer-time cooling slowdown helps small TPU regions set before the next pass.",
    "smooth_speed_discontinuity_area": "Smoothing speed transitions reduces visible speed bands in TPU.",
    "support_type": "Normal auto support is a Bambu-preserved support type for the slipper fixture.",
    "support_style": "Snug is a valid Bambu enum and avoids the organic-to-default substitution seen earlier.",
    "support_top_z_distance": "0.30 mm gives TPU supports air gap for removability.",
    "support_bottom_z_distance": "0.30 mm mirrors the top gap for removable TPU-on-TPU supports.",
    "support_interface_top_layers": "Zero top interface layers prevents TPU-on-TPU support roofs welding to the part.",
    "support_interface_bottom_layers": "Zero bottom interface layers avoids extra welded TPU support material.",
    "support_interface_speed": "Slow interface speed keeps optional support interfaces clean if re-enabled.",
    "support_interface_filament_flow": "Reduced interface flow keeps optional TPU interfaces easier to peel.",
    "support_on_build_plate_only": "Build-plate-only supports avoid scarring upper surfaces.",
    "brim_type": "Outer brim helps the flexible part hold the plate without a full raft.",
    "brim_width": "5 mm brim adds adhesion margin for long flexible prints.",
    "brim_object_gap": "0.12 mm gap keeps the brim from welding into the TPU part.",
    "raft_layers": "Rafts are avoided because TPU rafts are slow and difficult to remove.",
    "reduce_crossing_wall": "Avoiding wall crossings suppresses stringing across open TPU cavities.",
}

TPU_90A_CATEGORIES: CategoryMap = {
    "filament_type": "metadata",
    "support_type": "compatibility",
    "support_style": "compatibility",
    "brim_type": "compatibility",
    "raft_layers": "compatibility",
}

TPU_90A_HARDWARE_NOTES = (
    "Use an external spool path for 90A TPU; do not route soft TPU through an AMS unless the exact filament is explicitly AMS-compatible.",
    "Keep PTFE routing short and straight to reduce drag on the flexible strand.",
)

TPU_90A_PREFLIGHT_NOTES = (
    "Dry TPU at 50 C for 4-8 h before long prints, then feed from a dryer when possible.",
    "Clean textured PEI with high-purity IPA and avoid glue unless the plate has contaminated residue.",
    "Disable automatic flow dynamics calibration for soft TPU and use manual pressure advance.",
)

TPU_95A_FILAMENT_OVERRIDES: SettingOverrides = {
    "filament_type": ["TPU"],
    "filament_max_volumetric_speed": ["4.0"],
    "filament_retraction_length": ["0.8"],
    "filament_retraction_speed": ["35"],
    "filament_deretraction_speed": ["35"],
    "enable_pressure_advance": ["1"],
    "pressure_advance": ["0.030"],
    "fan_min_speed": ["40"],
    "fan_max_speed": ["80"],
    "close_fan_the_first_x_layers": ["1"],
    "additional_cooling_fan_speed": ["30"],
}

TPU_95A_PROCESS_OVERRIDES: SettingOverrides = {
    "outer_wall_speed": ["35"],
    "inner_wall_speed": ["55"],
    "small_perimeter_speed": ["25"],
    "sparse_infill_speed": ["70"],
    "top_surface_speed": ["25"],
    "initial_layer_speed": ["25"],
    "default_acceleration": ["4000"],
    "outer_wall_acceleration": ["2500"],
    "enable_overhang_speed": ["1"],
    "support_type": ["normal(auto)"],
    "support_style": ["snug"],
    "support_top_z_distance": ["0.25"],
    "support_bottom_z_distance": ["0.25"],
    "support_interface_top_layers": ["0"],
    "support_interface_bottom_layers": ["0"],
    "support_on_build_plate_only": ["1"],
    "brim_type": ["outer_only"],
    "brim_width": ["3"],
    "brim_object_gap": ["0.10"],
}

TPU_95A_REASONS: ReasonMap = {
    "filament_type": "Marks the profile as TPU so downstream reports group it with flexible-material rules.",
    "filament_max_volumetric_speed": "95A TPU is firmer than 90A, but still starts with a conservative MVS until calibrated.",
    "filament_retraction_length": "Slightly shorter retraction suits firmer TPU without over-stretching it.",
    "filament_retraction_speed": "Moderate retraction speed balances stringing control and filament stretch.",
    "filament_deretraction_speed": "Matching deretraction keeps restart pressure consistent.",
    "enable_pressure_advance": "Manual pressure advance gives a stable baseline for flexible filament.",
    "pressure_advance": "K = 0.030 is a conservative starting point for firmer TPU pending calibration.",
    "fan_min_speed": "95A TPU can accept more cooling than 90A while still needing bond caution.",
    "fan_max_speed": "80% caps cooling below rigid-filament assumptions.",
    "close_fan_the_first_x_layers": "Layer 1 keeps cooling off for PEI adhesion.",
    "additional_cooling_fan_speed": "Auxiliary fan remains limited to protect TPU layer bonding.",
    "outer_wall_speed": "Outer walls remain slower than rigid-filament defaults for surface stability.",
    "inner_wall_speed": "Firmer TPU can run moderate hidden-wall speeds.",
    "small_perimeter_speed": "Small perimeters stay slow to reduce corner blobs.",
    "sparse_infill_speed": "Firmer TPU permits faster infill while staying below MVS risk.",
    "top_surface_speed": "Top surfaces slow down to avoid smearing.",
    "initial_layer_speed": "First layers stay conservative for plate adhesion.",
    "default_acceleration": "Acceleration is reduced from rigid-filament defaults for flexible extrusion.",
    "outer_wall_acceleration": "Outer wall acceleration is lowered for cleaner TPU surfaces.",
    "enable_overhang_speed": "Overhang slowdown is enabled because flexible filament droops.",
    "support_type": "Normal auto support is the Bambu-compatible baseline.",
    "support_style": "Snug is the validated Bambu support style enum for removable supports.",
    "support_top_z_distance": "0.25 mm gives firmer TPU support gap while keeping support effective.",
    "support_bottom_z_distance": "0.25 mm mirrors the top support gap.",
    "support_interface_top_layers": "Zero top interface layers reduce the chance of TPU supports welding to the model.",
    "support_interface_bottom_layers": "Zero bottom interface layers avoid extra welded TPU support material.",
    "support_on_build_plate_only": "Build-plate-only supports avoid scarring flexible model surfaces.",
    "brim_type": "Outer brim adds adhesion without raft removal problems.",
    "brim_width": "3 mm brim is a moderate baseline for firmer TPU.",
    "brim_object_gap": "0.10 mm gap helps the brim peel away from TPU.",
}

TPU_95A_CATEGORIES: CategoryMap = {
    "filament_type": "metadata",
    "support_type": "compatibility",
    "support_style": "compatibility",
    "brim_type": "compatibility",
}

TPU_95A_HARDWARE_NOTES = (
    "Prefer external spool feeding for TPU unless the filament and profile are explicitly marked AMS-compatible.",
    "Keep the filament path low-friction because flexible filament drag can show up as under-extrusion.",
)

TPU_95A_PREFLIGHT_NOTES = (
    "Dry TPU at 50 C for 4-8 h when the spool history is unknown.",
    "Confirm the selected filament is not a special AMS-only profile before using AMS routing.",
)

SUNLU_TPU_90A_FILAMENT_OVERRIDES: SettingOverrides = _merge_overrides(
    TPU_90A_FILAMENT_OVERRIDES,
    {
        "filament_settings_id": ["SUNLU TPU 90A Slipper @BBL P2S"],
        "filament_vendor": ["SUNLU"],
        "filament_density": ["1.23"],
        "filament_cost": ["20.00"],
        "filament_diameter": ["1.75"],
        "filament_colour": ["#000000"],
        "default_filament_colour": ["#000000"],
        "nozzle_temperature_initial_layer": ["225"],
        "nozzle_temperature": ["225"],
        "cool_plate_temp": ["30"],
        "hot_plate_temp": ["45"],
        "hot_plate_temp_initial_layer": ["45"],
        "filament_max_volumetric_speed": ["2.5"],
        "filament_flow_ratio": ["1.0"],
    },
)

SUNLU_TPU_90A_PROCESS_OVERRIDES: SettingOverrides = _merge_overrides(
    TPU_90A_PROCESS_OVERRIDES,
    {
        "layer_height": ["0.20"],
        "initial_layer_print_height": ["0.20"],
        "line_width": ["0.42"],
        "initial_layer_line_width": ["0.50"],
        "outer_wall_line_width": ["0.40"],
        "inner_wall_line_width": ["0.45"],
        "top_surface_line_width": ["0.40"],
        "internal_solid_infill_line_width": ["0.45"],
        "sparse_infill_line_width": ["0.45"],
        "wall_loops": ["3"],
        "wall_generator": ["arachne"],
        "detect_thin_wall": ["0"],
        "precise_outer_wall": ["0"],
        "seam_position": ["back"],
        "staggered_inner_seams": ["1"],
        "seam_gap": ["15%"],
        "scarf_seam_type": ["none"],
        "top_surface_pattern": ["monotonic"],
        "bottom_surface_pattern": ["monotonic"],
        "top_shell_layers": ["4"],
        "top_shell_thickness": ["0.8"],
        "bottom_shell_layers": ["10"],
        "bottom_shell_thickness": ["2.0"],
        "sparse_infill_density": ["15%"],
        "sparse_infill_pattern": ["gyroid"],
        "infill_wall_overlap": ["25%"],
        "infill_anchor": ["2.5"],
        "infill_anchor_max": ["12"],
        "infill_combination": ["0"],
        "enable_internal_bridge_support": ["1"],
        "detect_overhang_wall": ["1"],
        "bridge_density": ["100%"],
        "bridge_flow": ["0.85"],
        "internal_bridge_flow": ["1.1"],
        "thick_bridges": ["0"],
        "make_overhang_printable": ["0"],
        "support_threshold_angle": ["60"],
        "apply_gap_fill": ["everywhere"],
        "filter_out_gap_fill": ["0.0"],
    },
)

SUNLU_TPU_90A_REASONS: ReasonMap = _merge_text(
    TPU_90A_REASONS,
    {
        "filament_settings_id": "Names the user filament preset generated from the slipper proof of concept.",
        "filament_vendor": "Records that the slipper lesson came from SUNLU TPU 90A.",
        "filament_density": "Uses SUNLU TPU density for mass and cost estimates.",
        "filament_cost": "Keeps the slipper-era cost basis visible in reports.",
        "filament_diameter": "Records standard 1.75 mm filament diameter for the Bambu P2S profile.",
        "filament_colour": "Carries the black SUNLU slipper profile color.",
        "default_filament_colour": "Carries the default black display color for generated profiles.",
        "nozzle_temperature_initial_layer": "225 C matched the slipper profile's steady TPU temperature.",
        "nozzle_temperature": "225 C was the SUNLU 90A slipper baseline for slow TPU wall speeds.",
        "cool_plate_temp": "Cool plate value remains explicit for profile completeness, though textured PEI is preferred.",
        "hot_plate_temp": "45 C keeps TPU adhered without overheating the 295 mm slipper sole.",
        "hot_plate_temp_initial_layer": "45 C keeps first-layer bed behavior consistent with later layers.",
        "filament_max_volumetric_speed": "2.5 mm3/s is the slipper-derived zero-drama MVS until a tower proves more.",
        "filament_flow_ratio": "1.0 keeps SUNLU flow neutral until a single-wall test suggests correction.",
        "layer_height": "0.20 mm balances TPU layer bonding and print time for footwear.",
        "initial_layer_print_height": "0.20 mm first layer absorbs small bed-level variation.",
        "line_width": "0.42 mm slightly over-widths default lines for better TPU side bonding.",
        "initial_layer_line_width": "0.50 mm widens the first layer for adhesion.",
        "outer_wall_line_width": "0.40 mm keeps exterior slipper dimensions crisp.",
        "inner_wall_line_width": "0.45 mm strengthens hidden TPU walls.",
        "top_surface_line_width": "0.40 mm keeps top surfaces clean without ironing.",
        "internal_solid_infill_line_width": "0.45 mm improves sole-layer bonding.",
        "sparse_infill_line_width": "0.45 mm gives sparse TPU lines more bonding area.",
        "wall_loops": "Three wall loops preserve slipper cushion while improving durability.",
        "wall_generator": "Arachne handles curved slipper walls without forcing thick blobs.",
        "detect_thin_wall": "Thin-wall detection is disabled because it caused blob risk on TPU curves.",
        "precise_outer_wall": "Precise outer walls are disabled to preserve Arachne's flexible line-width behavior.",
        "seam_position": "Back seam keeps the seam out of the toe flex zone.",
        "staggered_inner_seams": "Staggered inner seams avoid a single weak vertical column.",
        "seam_gap": "15% seam gap absorbs TPU ooze at line starts.",
        "scarf_seam_type": "Scarf seam is disabled because it can under-extrude on TPU curves.",
        "top_surface_pattern": "Monotonic top surfaces reduce seams that could catch socks.",
        "bottom_surface_pattern": "Monotonic bottom surfaces give uninterrupted ground contact.",
        "top_shell_layers": "Four top layers prevent the foot-bed from cratering into infill.",
        "top_shell_thickness": "0.8 mm top shell matches the four-layer slipper target.",
        "bottom_shell_layers": "Ten bottom layers create a durable 2.0 mm TPU wear surface.",
        "bottom_shell_thickness": "2.0 mm bottom shell protects the sole from early wear.",
        "sparse_infill_density": "15% gyroid was the slipper cushion compromise between collapse and stiffness.",
        "sparse_infill_pattern": "Gyroid gives isotropic flex for footwear.",
        "infill_wall_overlap": "25% overlap fights TPU infill-to-wall delamination.",
        "infill_anchor": "2.5 mm anchor stitches gyroid into the walls.",
        "infill_anchor_max": "12 mm keeps default anchoring instead of disabling it.",
        "infill_combination": "Infill combination is disabled to preserve every-layer TPU bonding.",
        "enable_internal_bridge_support": "Internal bridge support reinforces the heel cup without external scarring.",
        "detect_overhang_wall": "Overhang detection slows heel-cup curls before they droop.",
        "bridge_density": "100% bridge density avoids peel-prone partial TPU bridges.",
        "bridge_flow": "0.85 bridge flow reduces sag on external TPU bridges.",
        "internal_bridge_flow": "1.1 internal bridge flow welds the foot-bed surface to support below.",
        "thick_bridges": "Thick bridges are disabled because TPU sags when bridge paths get heavy.",
        "make_overhang_printable": "Geometry chamfering is avoided so PrintPipe does not change the slipper shape.",
        "support_threshold_angle": "60 degrees keeps supports targeted instead of blanketing sidewalls.",
        "apply_gap_fill": "Everywhere gap fill closes micro-voids that can become flex cracks.",
        "filter_out_gap_fill": "Zero filtering keeps small TPU voids filled instead of leaving crack starters.",
    },
)

SUNLU_TPU_90A_CATEGORIES: CategoryMap = _merge_text(
    TPU_90A_CATEGORIES,
    {
        "filament_settings_id": "metadata",
        "filament_vendor": "metadata",
        "filament_density": "metadata",
        "filament_cost": "metadata",
        "filament_diameter": "metadata",
        "filament_colour": "metadata",
        "default_filament_colour": "metadata",
        "cool_plate_temp": "compatibility",
        "hot_plate_temp": "behavior",
        "hot_plate_temp_initial_layer": "behavior",
        "support_threshold_angle": "behavior",
    },
)

SUNLU_TPU_90A_HARDWARE_NOTES = (
    "AMS incompatible: use the external spool holder or a dryer feed path; soft SUNLU TPU 90A can buckle in the AMS/Bowden path.",
    "Mount the spool on a low-friction holder and keep PTFE short and straight.",
    "Use textured PEI for the slipper profile; avoid smooth/cool plates that can grip TPU too aggressively.",
)

SUNLU_TPU_90A_PREFLIGHT_NOTES = (
    "Dry SUNLU TPU 90A at 50 C for 4-8 h before the slipper print and feed from the dryer for long runs.",
    "Disable AMS in Bambu Studio and select the external spool path before slicing.",
    "Cold-pull the nozzle if the previous print was not TPU.",
    "Clean textured PEI with >91% IPA before the first layer.",
)

_RULES: dict[str, TpuMaterialRule] = {
    "tpu-90a-foundation": _build_rule(
        slug="tpu-90a-foundation",
        name="TPU 90A Foundation",
        shore_hardness="90A",
        filament_overrides=TPU_90A_FILAMENT_OVERRIDES,
        process_overrides=TPU_90A_PROCESS_OVERRIDES,
        hardware_notes=TPU_90A_HARDWARE_NOTES,
        preflight_notes=TPU_90A_PREFLIGHT_NOTES,
        reasons=TPU_90A_REASONS,
        categories=TPU_90A_CATEGORIES,
    ),
    "tpu-95a-foundation": _build_rule(
        slug="tpu-95a-foundation",
        name="TPU 95A Foundation",
        shore_hardness="95A",
        filament_overrides=TPU_95A_FILAMENT_OVERRIDES,
        process_overrides=TPU_95A_PROCESS_OVERRIDES,
        hardware_notes=TPU_95A_HARDWARE_NOTES,
        preflight_notes=TPU_95A_PREFLIGHT_NOTES,
        reasons=TPU_95A_REASONS,
        categories=TPU_95A_CATEGORIES,
    ),
    "sunlu-tpu-90a-slipper": _build_rule(
        slug="sunlu-tpu-90a-slipper",
        name="SUNLU TPU 90A Slipper",
        shore_hardness="90A",
        filament_overrides=SUNLU_TPU_90A_FILAMENT_OVERRIDES,
        process_overrides=SUNLU_TPU_90A_PROCESS_OVERRIDES,
        hardware_notes=SUNLU_TPU_90A_HARDWARE_NOTES,
        preflight_notes=SUNLU_TPU_90A_PREFLIGHT_NOTES,
        reasons=SUNLU_TPU_90A_REASONS,
        categories=SUNLU_TPU_90A_CATEGORIES,
    ),
}


def available_tpu_rules() -> dict[str, TpuMaterialRule]:
    """Return all known TPU rule variants keyed by stable slug."""
    return copy.deepcopy(_RULES)


def get_tpu_rule(slug: str) -> TpuMaterialRule:
    """Return one TPU material rule by slug."""
    try:
        return copy.deepcopy(_RULES[slug])
    except KeyError as exc:
        raise KeyError(f"unknown TPU material rule: {slug}") from exc


__all__ = [
    "TpuMaterialRule",
    "available_tpu_rules",
    "get_tpu_rule",
]
