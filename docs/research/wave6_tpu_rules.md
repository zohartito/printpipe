# Wave 6 TPU Material Rules

Status: Wave 6 Agent C handoff for roadmap items 76, 77, 78, and 81.

## Sources Read

- `docs/APP_ROADMAP.md`
- `docs/research/wave1_bambu_schema.md`
- `src/printpipe/bambu/profiles/core.py`
- `/Users/zohartito/Desktop/slipper_3d/PRINT_SETTINGS.md`
- `/Users/zohartito/Desktop/slipper_3d/output/SUNLU TPU 90A Slipper @BBL P2S.json`
- `/Users/zohartito/Desktop/slipper_3d/output/0.20mm Slipper TPU 90A @BBL P2S.json`

## Implemented Shape

`src/printpipe/materials/tpu.py` now defines a TPU rule catalog with:

- `tpu-90a-foundation`
- `tpu-95a-foundation`
- `sunlu-tpu-90a-slipper`

Each rule separates:

- `filament_overrides`: Bambu-style filament profile values.
- `process_overrides`: Bambu-style process profile values.
- `hardware_notes`: printer, spool path, AMS, and plate constraints.
- `preflight_notes`: drying, calibration, plate prep, and last-mile checks.
- `reasons`: one human-readable reason for every override key.
- `categories`: settings-delta categories for receipt rows.

The rule object exposes `combined_overrides()` for settings reports that need a
single map, and `delta_metadata()` for passing `categories` and `reasons` into
`generate_settings_delta_rows`.

## Preserved SUNLU TPU 90A Slipper Lessons

The SUNLU slipper rule preserves these explicit slipper-derived behaviors:

| Area | Preserved Rule |
|---|---|
| Max volumetric speed | `filament_max_volumetric_speed = ["2.5"]` as the conservative first-print ceiling. |
| Manual pressure advance | `enable_pressure_advance = ["1"]` and `pressure_advance = ["0.040"]`; do not rely on auto flow dynamics for soft TPU. |
| Slow print speeds | Outer wall 25 mm/s, top surface 20 mm/s, small perimeters 20 mm/s, initial layer 20 mm/s. |
| Lower cooling | Body fan 30-60%, auxiliary fan 20%, first layer fan off. |
| AMS note | SUNLU TPU 90A is marked AMS incompatible; use external spool or dryer feed. |
| Support removability | Normal(auto) support, snug style, 0.30 mm top/bottom Z gap, zero interface layers, reduced interface flow, build-plate-only supports. |
| Brim removability | Outer brim, 5 mm width, 0.12 mm object gap to avoid welding brim into TPU. |
| Footwear strength | 3 walls, 10 bottom shell layers, 15% gyroid, 25% infill-wall overlap, no infill combination. |

## TPU 90A Foundation

The 90A foundation is intentionally conservative. It captures the soft-flexible
baseline without tying the rule to SUNLU metadata:

- MVS starts at 3.0 mm3/s pending calibration.
- Retraction is short and moderate: 1.0 mm at 30 mm/s.
- Manual PA starts at K = 0.040.
- Body cooling is capped at 60%.
- Process speeds are slipper-class slow.
- Snug supports and removable TPU-on-TPU gaps are the support baseline.

Hardware and preflight notes require external spool style routing unless a
specific filament is explicitly AMS-compatible, short and straight PTFE, drying
at 50 C for 4-8 h, clean textured PEI, and manual pressure advance.

## TPU 95A Foundation

The 95A foundation is firmer and less slipper-specific, but still keeps flexible
filament guardrails:

- MVS starts at 4.0 mm3/s pending calibration.
- Retraction starts at 0.8 mm at 35 mm/s.
- Manual PA starts at K = 0.030.
- Cooling can rise to 40-80%, still below rigid-filament assumptions.
- Speeds are faster than 90A but remain below PLA/PETG expectations.
- Snug, build-plate-only supports remain the default for removable support.

The AMS note is softer for 95A: prefer external spool feeding unless the exact
filament and profile are explicitly marked AMS-compatible.

## Settings Delta Compatibility

The tests verify that the SUNLU 90A slipper rule can feed existing settings
delta generation:

```python
rows = generate_settings_delta_rows(
    {},
    rule.combined_overrides(),
    categories=rule.categories,
    reasons=rule.reasons,
    extruder_count=1,
)
```

The rule builder refuses to construct a rule if any override lacks a reason.
That keeps roadmap item 81 attached to the material-rule data rather than
depending on later report code to catch missing explanations.

## Open Follow-Ups

- Validate TPU 95A numeric defaults against a real Bambu/Orca TPU 95A profile
  when that fixture is available.
- Wire material selection into the run pipeline after the other material-family
  rule catalogs exist.
- Expand enum validation beyond `support_style` before writing additional
  process enum overrides.
