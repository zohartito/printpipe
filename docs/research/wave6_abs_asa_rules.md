# Wave 6 ABS/ASA Material Rule Foundation

Status: ABS/ASA foundation for roadmap items 76, 77, 78, and 81.

## Scope

This wave adds conservative rule objects for the ABS/ASA material family. The
rules are intentionally foundations, not brand-specific tuned presets. They
provide:

- filament overrides for temperature, bed targets, chamber target, flow cap,
  and cooling
- process overrides for brim/bed adhesion
- category and reason maps suitable for settings delta receipts
- preflight notes for operator checks that should not be blindly encoded as
  slicer settings

## Profile-Key Findings

Local Bambu Studio profiles confirm these ABS/ASA-related keys are present in
filament or process profiles:

- `filament_type`
- `nozzle_temperature`
- `nozzle_temperature_initial_layer`
- `hot_plate_temp`
- `hot_plate_temp_initial_layer`
- `textured_plate_temp`
- `textured_plate_temp_initial_layer`
- `eng_plate_temp`
- `eng_plate_temp_initial_layer`
- `chamber_temperatures`
- `filament_max_volumetric_speed`
- `fan_min_speed`
- `fan_max_speed`
- `slow_down_layer_time`
- `brim_width`
- `brim_object_gap`

`brim_type` is already used by PrintPipe's TPU fixture overlay and is grouped
under the brim category here, but it should still be covered by the broader
enum/schema validation work before arbitrary values are expanded.

## Conservative Defaults

ABS starts with a moderate generic ABS profile:

- nozzle: 260 C print / 260 C initial layer
- bed: 100 C for hot, textured, and engineering plate targets
- chamber target: 60 C where supported by the selected printer/profile
- max volumetric speed: 10 mm3/s
- cooling: 0% minimum fan, 35% maximum fan, 12 s layer-time slowdown
- brim: outer-only, 8 mm width, 0.1 mm object gap

ASA differs intentionally:

- nozzle: 255 C print / 260 C initial layer
- max volumetric speed: 8 mm3/s
- cooling: 0% minimum fan, 25% maximum fan, 12 s layer-time slowdown

The lower ASA flow and fan cap are conservative starting points until a
brand-specific ASA profile or calibration data is available.

## Preflight-Only Guidance

These items are included as preflight notes because they depend on the printer,
room, enclosure, filtration, and model geometry:

- chamber: use an enclosed printer and let the chamber/air volume warm before
  judging first-layer stability
- ventilation: use appropriate room ventilation or filtration for ABS/ASA
- warping: avoid drafts, cold plates, and large sharp corners; split or reorient
  large flat parts when possible
- preheat: preheat the bed and enclosure before larger jobs

Only `chamber_temperatures` is represented as a slicer-facing override because
that key is visible in Bambu ABS/ASA profiles. Ventilation, warping, and preheat
remain operator notes.

## Receipt Categories

The ABS/ASA rules attach reasons to every changed setting and group deltas into
receipt categories:

- `bed_adhesion`: bed temperature keys
- `brim`: brim type, width, and object gap
- `cooling`: fan and layer-time cooling keys
- `temperature`: nozzle temperature keys
- `chamber`: chamber target key
- `flow`: max volumetric speed
- `metadata`: material type

The focused test file verifies that `generate_settings_delta_rows` can consume
the combined overrides with the category and reason maps and produce rows
without missing reasons.
