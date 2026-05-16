# Wave 6 PLA Material Rules

Status: Wave 6 Agent A foundation for roadmap items 76, 77, 78, and 81.

## Scope

This pass adds a dependency-light PLA rule structure in
`src/printpipe/materials/pla.py`. It is intentionally a foundation, not a tuned
printer profile.

Covered:

- Material family entries for plain PLA and PLA+ intent.
- Separate filament and process override mappings.
- A required reason for every emitted override key.
- Category hints shaped for the existing settings delta report.
- Copy-safe `build_pla_overrides(variant="pla")` output for downstream profile
  assembly.

Not covered:

- Brand-specific nozzle, bed, flow, cooling, or speed tuning.
- Printer-specific tuning for P2S or any other Bambu model.
- Support, brim, pressure advance, or retraction policies copied from the TPU
  slipper proof of concept.
- Validation that these values are optimal for a specific PLA spool.

## Data Shape

`PLA_RULES` maps canonical variants to `MaterialRuleSet` instances:

```python
PLA_RULES["pla"]
PLA_RULES["pla_plus"]
```

Each rule stores:

- `profile_intent`: human-readable guidance for the profile source to clone.
- `filament_overrides`: material identity metadata.
- `process_overrides`: conservative process intent shared by both variants.
- `reasons`: one human-readable reason per override key.
- `categories`: `metadata` or `compatibility` values for settings delta rows.

`build_pla_overrides()` returns plain dictionaries so profile assembly and report
generation do not depend on the dataclass internals.

## Current Overrides

Plain PLA filament overrides:

```json
{
  "filament_type": ["PLA"],
  "filament_vendor": ["Generic"]
}
```

PLA+ filament overrides:

```json
{
  "filament_type": ["PLA"],
  "filament_vendor": ["Generic PLA+"]
}
```

Shared process overrides:

```json
{
  "layer_height": ["0.20"],
  "wall_loops": ["2"]
}
```

The shared process values are compatibility intent only: start from a common
0.20 mm process and a two-wall baseline, then let later geometry, strength, and
validated material rules make real tuning decisions.

## Delta Receipt Compatibility

The returned object can feed the existing profile delta helper directly:

```python
result = build_pla_overrides("pla")
custom = {
    **result["filament_overrides"],
    **result["process_overrides"],
}
rows = generate_settings_delta_rows(
    defaults,
    custom,
    categories=result["categories"],
    reasons=result["reasons"],
)
```

The tests assert every emitted key has a non-empty reason so roadmap item 81
remains a hard contract for material rules.

## Variant Notes

`pla` means generic PLA intent. It should clone a Generic PLA baseline from the
selected Bambu/Orca-compatible profile source and add only neutral material
identity plus compatibility intent.

`pla_plus` means PLA+ or PLA Tough intent. It still uses the PLA material family
for profile compatibility and records the plus intent in metadata. Temperature,
flow, cooling, and strength behavior must come from a validated profile source
or a future rule pass with evidence.

Accepted aliases:

- `pla`, `generic_pla`
- `pla+`, `pla_plus`, `plus`

## Validation Added

`tests/test_materials_pla.py` covers:

- Presence of plain PLA and PLA+ rule intents.
- Filament/process override keys and reason coverage.
- Copy-safe return values.
- Guardrails against TPU-specific keys or text leaking into PLA rules.
- Direct consumption by `generate_settings_delta_rows`.
- Clear errors for unsupported variants.
