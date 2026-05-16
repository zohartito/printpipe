# Wave 6 PC/PA Material Rule Foundation

Status: Wave 6 Agent E implementation note for roadmap items 76, 77, 78, and 81.

## Sources Read

- `docs/APP_ROADMAP.md`
- `docs/research/wave1_bambu_schema.md`
- `src/printpipe/bambu/profiles/core.py`
- Local Bambu Studio profile samples for PC, PA, PA-CF, and common process keys under `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/`

## Implementation Contract

The foundation lives in `src/printpipe/materials/pc_pa.py`.

It defines `MaterialRule` objects for:

- `PC`
- `PA`
- `PA-CF`

Each rule carries:

- `filament_overrides`
- `process_overrides`
- `setting_categories`
- `setting_reasons`
- `preflight_notes`

`MaterialRule.profile_overrides()` returns a merged mapping that can be passed directly to `generate_settings_delta_rows(...)` with the rule's categories and reasons. The module validates at import time that every emitted override has both a category and a reason.

## Preflight Gates

Moisture is intentionally stronger than a normal warning for nylon materials:

- PA has a `hard_gate` preflight note: do not start unless the filament was dried immediately before printing and shows no popping, steam, or surface fuzz.
- PA-CF has the same moisture hard gate, plus a `hard_gate` hardened-nozzle note because carbon fiber fill is abrasive.
- PC still has a drying warning because wet PC prints poorly, but PC moisture is not marked as a hard gate in this foundation.

The rules do not encode drying time or drying temperature yet. Those should come from vendor-specific filament guidance or a vetted PrintPipe drying table.

## Foundation Overrides

The values are conservative starting points, not final tuned profiles.

| Material | Temperature | Bed Adhesion | Chamber/Preheat | Cooling | Strength/Shell |
| --- | --- | --- | --- | --- | --- |
| PC | 280 C print, 270 C first layer, MVS 8 | 100 C plate targets, outer brim, 8 mm brim | 60 C chamber target | Very low fan, capped overhang fan | 4 walls, 5 top, 5 bottom, 25% infill |
| PA | 260 C print and first layer, MVS 8 | 90 C plate targets, outer brim, 8 mm brim | 45 C chamber target | Low to moderate fan cap | 4 walls, 5 top, 5 bottom, 25% infill |
| PA-CF | 285 C print and first layer, MVS 6 | 100 C plate targets, outer brim, 10 mm brim | 55 C chamber target | Low fan cap, moderate overhang fan | 4 walls, 5 top, 5 bottom, 30% infill |

The bed-temperature overrides set `textured_plate_temp`, `hot_plate_temp`, and `eng_plate_temp` plus their first-layer variants because profile defaults vary by plate and source profile.

## Categories

The setting categories are foundation-level receipt labels:

- `bed_adhesion`
- `chamber_preheat`
- `cooling`
- `strength_shell`
- `temperature`
- `throughput`
- `material_identity`

These are intentionally more specific than the generic `behavior` bucket so reports can explain why a rule changed each setting.

## Limitations

- These rules do not select a printer profile or verify whether a printer can safely hold the target chamber/bed conditions.
- These rules do not add support heuristics; support burden should remain object- and orientation-aware.
- These rules do not replace vendor PA, PA-CF, or PC drying guidance.
- PA-CF hardware compatibility is represented as a preflight hard gate, not a Bambu profile setting, because the relevant installed profiles did not expose a stable hardened-nozzle override key.
- Real dogfood prints should still update this table, especially for plate adhesive, brim gap, cooling, and chamber targets.

## Verification

Targeted tests:

```text
.venv/bin/python -m pytest tests/test_materials_pc_pa.py
```

Current result:

```text
11 passed
```
