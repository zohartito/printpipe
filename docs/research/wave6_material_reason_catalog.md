# Wave 6 Material Reason Catalog Foundation

Status: foundation complete

## Scope

Wave 6 introduces the shared material registry and reason catalog foundation for
roadmap items 76 and 81:

- Define material families without coupling the shared registry to PLA, PETG,
  TPU, ABS/ASA, PC, PA, or future family modules.
- Attach a human-readable reason to every changed Bambu filament or process
  setting.
- Attach a category to every changed setting so reports can group material
  behavior, compatibility, metadata, and normalization decisions.

The shared code lives in `src/printpipe/materials/core.py`. It intentionally
does not import concrete material-family modules. Concrete families should
define their own `MaterialRuleSet` instances and register them from their own
module or an integration layer.

## MaterialRuleSet Contract

Each material rule set declares:

- `material_id`: stable machine id, such as `tpu-90a` or `pla`.
- `display_name`: user-facing material family or preset name.
- `base_profile_hint`: suggested upstream Bambu/Orca profile to inherit from.
- `filament_overrides`: settings applied to the filament profile overlay.
- `process_overrides`: settings applied to the process profile overlay.
- `reasons`: reason catalog entries keyed by setting.
- `categories`: category catalog entries keyed by setting.
- `preflight_notes`: material-specific checklist notes for the final report.

Reason and category keys may be scope-qualified:

```text
filament.nozzle_temperature
process.support_style
```

Unscoped keys are allowed only for settings where the same annotation is correct
in every profile scope:

```text
fan_min_speed
```

Scope-qualified annotations win over unscoped annotations when both exist.

## Reason Catalog Rule

Every intentional override must have a reason. A reason should explain the print
behavior or compatibility outcome, not repeat the setting name.

Good:

```text
process.support_style = Use snug supports for easier flexible-material cleanup.
```

Not enough:

```text
process.support_style = Change support style.
```

If a setting is changed only to preserve identity or profile metadata, it still
needs a reason. For example, a filament vendor label should say that it records
the selected brand/material in the receipt and Bambu profile.

Rows without a reason receive the existing fallback value:

```text
reason not assigned
```

The existing `summarize_delta_rows` report helper counts these rows as
`missing_reasons`. A material rule set is not beta-ready while its material
delta rows have a non-zero missing reason count.

## Category Catalog Rule

Every intentional override must have a category. Categories should use the
existing settings-delta vocabulary unless a later roadmap item adds a documented
category:

- `behavior`: changes print behavior, such as temperature, speed, support, wall,
  cooling, or adhesion.
- `compatibility`: keeps the profile valid for Bambu/Orca or a selected printer.
- `metadata`: records identity, naming, vendor, material, or receipt context.
- `normalization/no-op`: preserves an inherited value for clarity without a
  semantic behavior change.

The shared delta helper falls back to `behavior` because the underlying Bambu
profile delta engine already uses that default. Concrete material modules should
still provide explicit categories so reviewers can see that each override was
classified deliberately.

## Delta Flow

`material_delta_rows(defaults, rule_set, profile_scope=...)`:

1. Starts with resolved profile defaults.
2. Applies the rule set's scoped overrides without mutating the defaults.
3. Calls the existing `generate_settings_delta_rows` normalization helper.
4. Adds `profile_scope` and `material_id` to each row.

This keeps material receipts compatible with existing Bambu settings reports
while giving downstream code enough context to show whether a change came from
the filament or process side of a material family.

## Registry Rule

The registry exposes:

- `register_material_rules(rule_set, replace=False)`
- `get_material_rules(material_id)`
- `list_material_rules()`

The shared module should stay generic. Do not import concrete PLA, PETG, TPU,
ABS/ASA, PC, or PA modules from `printpipe.materials.core` or
`printpipe.materials.__init__`; that would create circular ownership conflicts
as family agents add material-specific rules in parallel.

## Review Checklist For New Material Families

Before a new material family is marked ready:

- Every key in `filament_overrides` has a matching `filament.<key>` reason.
- Every key in `filament_overrides` has a matching `filament.<key>` category.
- Every key in `process_overrides` has a matching `process.<key>` reason.
- Every key in `process_overrides` has a matching `process.<key>` category.
- `material_delta_rows` reports the expected semantic changes only.
- `summarize_delta_rows(material_delta_rows(...))["missing_reasons"] == 0`.
- Enum-valued process settings are covered by the Bambu enum validator before
  bundling.
- Preflight notes are concrete actions a user can check before printing.
