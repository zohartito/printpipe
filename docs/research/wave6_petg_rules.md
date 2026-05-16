# Wave 6 PETG Material Rule Foundation

Status: defaults-derived foundation, not yet dogfood validated.

## Sources Read

- `docs/APP_ROADMAP.md`
- `docs/research/wave1_bambu_schema.md`
- `src/printpipe/bambu/profiles/core.py`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/filament/Generic PETG @base.json`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/filament/Generic PETG @BBL P2S.json`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/filament/Bambu PETG Basic @base.json`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/filament/Bambu PETG Basic @BBL P2S 0.4 nozzle.json`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/process/fdm_process_common.json`
- `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/process/0.20mm Standard @BBL P2S.json`
- `/Users/zohartito/Desktop/slipper_3d/PRINT_SETTINGS.md`

## Scope

Roadmap items 76, 77, 78, and 81 need material-family rules, filament overrides,
process overrides, and reasons for every changed setting. This wave adds the PETG
foundation only:

- `PETG_RULES["petg-foundation"]`
- `build_petg_overrides()`
- settings-delta-compatible `categories` and `reasons`

The rules are intentionally conservative. They are derived from installed Bambu
PETG defaults and should remain marked `defaults-derived/unvalidated` until a
PETG fixture is sliced, previewed, and physically dogfooded.

## Rule Categories

| Category | Foundation keys | Rationale |
| --- | --- | --- |
| `bed_adhesion` | `textured_plate_temp_initial_layer`, `textured_plate_temp`, `hot_plate_temp_initial_layer`, `hot_plate_temp`, `first_x_layer_fan_speed`, `brim_width`, `brim_object_gap`, `initial_layer_speed`, `initial_layer_infill_speed` | PETG benefits from a warm bed and fan-off first layer, but can bond aggressively to PEI. The 70 C bed target and 0.1 mm brim gap come from Bambu PETG/common defaults. |
| `cooling` | `fan_min_speed`, `fan_max_speed`, `overhang_fan_speed`, `fan_cooling_layer_time`, `slow_down_layer_time` | Bambu PETG Basic P2S uses restrained part cooling versus Generic PETG. The foundation caps cooling until PrintPipe has PETG dogfood evidence. |
| `mvs_speed` | `filament_max_volumetric_speed`, `outer_wall_speed`, `inner_wall_speed`, `sparse_infill_speed`, `internal_solid_infill_speed`, `top_surface_speed`, `travel_speed` | Bambu PETG Basic base uses 8 mm3/s MVS. Process speed caps are below fast P2S defaults so MVS remains the primary limiter. |
| `stringing_retraction` | `filament_retraction_length`, `filament_z_hop_types`, `filament_wipe`, `filament_wipe_distance`, `reduce_crossing_wall`, `max_travel_detour_distance` | PETG stringing is handled at a foundation level with Bambu PETG Basic P2S wipe/retract values plus avoid-crossing-walls. |
| `temperature_flow` | `nozzle_temperature_initial_layer`, `nozzle_temperature`, `filament_flow_ratio` | Uses moderate Bambu PETG Basic temperatures and the PETG 0.95 flow-ratio baseline. |
| `metadata` | `filament_type`, `filament_vendor` | Identifies the material family without claiming brand-specific tuning. |

## Validation Notes

- Every emitted override key has a human-readable reason for settings delta rows.
- `tests/test_materials_petg.py` verifies keys, reason coverage, copy safety, and
  compatibility with `generate_settings_delta_rows`.
- The rules do not validate slicer enum values beyond using values observed in
  Bambu profile JSONs.
- The PETG foundation does not replace brand-specific profiles. A future PETG
  dogfood pass should compare these overrides against a resolved inherited
  profile and trim no-op rows.

## Open Follow-Ups

- Slice and inspect a PETG fixture on the target Bambu printer.
- Run an MVS tower for the selected PETG spool before raising the 8 mm3/s cap.
- Confirm whether `reduce_crossing_wall` plus an 80 mm detour is worth the time
  cost on PETG objects with complex interiors.
- Decide whether PETG should register itself in the material registry at import
  time or remain an explicit catalog import like the PLA foundation.
