# Wave 1 Bambu Schema and 3MF Requirements

Status: Wave 1 research handoff from the slipper proof of concept

## Sources Read

- `/Users/zohartito/Desktop/slipper_3d/3mf_signature_findings.md`
- `/Users/zohartito/Desktop/slipper_3d/build_3mf.py`
- `/Users/zohartito/Desktop/slipper_3d/profile_sources/**`
- `/Users/zohartito/Desktop/slipper_3d/output/SUNLU TPU 90A Slipper @BBL P2S.json`
- `/Users/zohartito/Desktop/slipper_3d/output/0.20mm Slipper TPU 90A @BBL P2S.json`
- `/Users/zohartito/Desktop/slipper_3d/AUDIT.md`
- `/Users/zohartito/Desktop/slipper_3d/RETROSPECTIVE.md`

## Bambu-Native 3MF Requirements

PrintPipe must treat an OPC-valid `.3mf` as insufficient. The bundle is only
successful if Bambu Studio opens it as a Bambu-native project and preserves
settings, profiles, and placement.

Required archive members for the current single-object, single-plate v1 shape:

- `[Content_Types].xml`
- `_rels/.rels`
- `3D/3dmodel.model`
- `Metadata/project_settings.config`
- `Metadata/model_settings.config`
- `Metadata/slice_info.config`
- `Metadata/plate_1.png`
- `Metadata/plate_no_light_1.png`

The decisive native signature is inside `3D/3dmodel.model`:

- Root model uses `unit="millimeter"`.
- Root model declares the Bambu namespace:
  `xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"`.
- It contains `<metadata name="Application">BambuStudio-<semver></metadata>`.
  The literal `BambuStudio-` prefix is the flag Bambu Studio checks.
- It contains `<metadata name="BambuStudio:3mfVersion">1</metadata>`.
  This is not the decisive flag, but native files include it and PrintPipe
  should emit it for parity.
- Objects and build items should include production namespace UUIDs.

`Metadata/project_settings.config` must be a flattened project settings JSON,
not a user filament JSON renamed into place. Its top-level header must begin as:

```json
{
  "name": "project_settings",
  "from": "project",
  "version": "02.04.00.70"
}
```

The exact version can move with the selected Bambu Studio/profile source, but it
must be semver-parseable and consistent with the emitted `Application` metadata.
The slipper project used `BambuStudio-02.04.00.70` because that matched the
native reference bundle dissected there.

`project_settings.config` must include resolved machine, process, and filament
settings plus explicit IDs:

- `filament_settings_id`
- `print_settings_id`
- `printer_settings_id`
- `printer_model`
- `printer_variant`
- `nozzle_diameter`
- `printable_height`

If `Application` does not start with `BambuStudio-`, Bambu Studio classifies the
file as foreign. If `project_settings.config` does not parse as project settings,
the loader can end up with an empty config and show the warning that it will load
geometry and color only. That is a failed PrintPipe run.

## Profile Inheritance Rules

PrintPipe should mirror the slipper project's profile strategy: clone official
Bambu profiles and write small user overlays, then flatten only at 3MF bundle
time.

Profile source lookup order:

1. Run-local or version-pinned profile cache, shaped like
   `profile_sources/{filament,process,machine,vendor}`.
2. Installed Bambu Studio resources at
   `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL`.

Inheritance chains discovered in the slipper project:

- Filament:
  `SUNLU TPU 90A Slipper @BBL P2S` -> `Bambu TPU 90A @BBL P2S` ->
  `Bambu TPU 90A @base` -> `fdm_filament_tpu` -> `fdm_filament_common`.
- Process:
  `0.20mm Slipper TPU 90A @BBL P2S` -> `0.20mm Standard @BBL P2S` ->
  `fdm_process_single_0.20` -> `fdm_process_single_common` ->
  `fdm_process_common`.
- Machine:
  `Bambu Lab P2S 0.4 nozzle` -> `fdm_bbl_3dp_001_common` ->
  `fdm_machine_common`.

Resolution rules:

- Walk `inherits` rootward with cycle detection.
- Merge root to leaf; child values overwrite parent values.
- Standalone user preset JSONs must keep `name`, `inherits`, `from`, `type`,
  `version`, and user-facing overrides.
- User presets must use `from: "User"` with that capitalization.
- User presets must not copy system `setting_id` values.
- Standalone profile values should generally be `[string]` arrays because Bambu
  profile schema is extruder-indexed.
- Flattened `project_settings.config` should drop profile-only metadata such as
  `inherits`, `instantiation`, source `from`, and `type`.
- Bundle merge order should be machine -> process -> filament, matching the
  slipper bundler's collision behavior where the most user-facing scope wins.

## Enum Validation Needs

Invalid enum values are dangerous because Bambu Studio may silently replace them
with defaults while still continuing the load or slice. PrintPipe must validate
enum-valued settings before writing profiles or bundles.

Known slipper finding:

- `support_style: "organic"` is invalid in Bambu Studio 2.6 and was replaced
  with `default`.
- Valid `support_style` values found by source inspection were `default` and
  `snug`.
- `support_type` is a separate enum. Do not infer its values from
  `support_style`; values such as `normal(auto)` and `tree(auto)` belong here.

Implementation rules:

- Maintain a schema table for enum keys used by PrintPipe overrides.
- Derive enum values from Bambu Studio source or a vetted schema, not from
  community terminology or UI labels.
- Treat slicer log messages like `Found legacy configuration values,
  substituted` as a blocker unless every substitution is explicitly allowlisted.
- Include enum validation in the settings receipt: key, value, schema source,
  and pass/fail.
- At minimum, validate process enums for support, brim, seam, wall generator,
  infill/surface patterns, ironing, raft, and any material-specific override
  PrintPipe writes.

## GUI vs CLI Transform Lessons

Bambu Studio GUI and CLI do not behave identically around bed placement.

Slipper lessons to preserve:

- The CLI `--load-settings` / `--load-filaments` path ignored the intended
  `printable_area` and fell back to a 200 x 200 mm bed in one path.
- A Bambu-native 3MF with embedded project settings was more reliable than
  passing loose settings to the CLI.
- CLI-only success was not enough. A prior artifact sliced headlessly but opened
  in the GUI with the object over the plate boundary.
- The robust final pattern was: keep the mesh origin-centered and Z-dropped,
  then express bed placement through 3MF transforms/`model_settings.config`
  using the selected printer's bed center, such as `128,128,0` for a 256 x 256
  P2S plate.
- Do not bake a bed-center translation into STL vertices and then also apply a
  bed-center 3MF transform.

PrintPipe must have both structural and behavioral checks:

- Validate the mesh bounds after all local transforms.
- Validate the 3MF build-item transform and `model_settings.config` part matrix.
- Run the Bambu CLI slice gate.
- Keep a GUI-open verification path for dogfood fixtures and any transform logic
  changes, because CLI acceptance alone missed the slipper GUI failure.

## Installed Profile Paths on macOS

Canonical app-shipped profiles:

```text
/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/
  filament/
  process/
  machine/
  vendor/
```

User profile root:

```text
~/Library/Application Support/BambuStudio/user/
```

User preset destinations:

```text
~/Library/Application Support/BambuStudio/user/<numeric_user_id>/filament/
~/Library/Application Support/BambuStudio/user/<numeric_user_id>/process/
~/Library/Application Support/BambuStudio/user/<numeric_user_id>/machine/
~/Library/Application Support/BambuStudio/user/default/filament/
~/Library/Application Support/BambuStudio/user/default/process/
~/Library/Application Support/BambuStudio/user/default/machine/
```

The slipper machine had a cloud-synced user directory:

```text
~/Library/Application Support/BambuStudio/user/1676299444/
```

Install requirements:

- Prefer a numeric `user/<id>/` directory when present; fall back to
  `user/default/`.
- Create `filament/`, `process/`, or `machine/` subdirectories if missing.
- Do not write into the app bundle's `Resources/profiles/BBL`; read from it or
  cache from it.
- Refuse profile installation while Bambu Studio is running because it caches
  presets at launch.
- Strip `com.apple.quarantine` from generated/downloaded JSONs before install.
- Expect Bambu Studio to generate `.info` sidecars; PrintPipe should not depend
  on writing those manually.

## Settings Delta Normalization

PrintPipe's settings report must compare behavior, not raw JSON formatting.
The slipper retrospective showed naive diffs over-count changes and confuse
users.

Normalize before diffing:

- Resolve the full inherited parent chain first.
- Treat singleton arrays and scalar values as equal when their semantic value is
  equal.
- Treat duplicated per-extruder arrays as equal to the same singleton value
  where the selected printer has one extruder, e.g. `["225", "225"]` equals
  `["225"]` for a single-nozzle P2S report.
- Compare numeric strings numerically, so `0.2`, `0.20`, and `["0.200"]` can
  collapse to the same value.
- Compare percentages as percentages, not opaque strings.
- Preserve special sentinel strings such as `nil`; do not coerce them to zero.
- Categorize each delta as `behavior`, `metadata`, `compatibility`, or
  `normalization/no-op`.
- Require a human-readable reason for every intentional behavior delta.

The slipper profiles illustrate why this matters. Several explicit keys were
redeclared for clarity but were semantically inherited unchanged. The real
behavior groups were SUNLU identity/material metadata, TPU-safe speeds and
accelerations, stronger shell/sole settings, snug support generation, bed
adhesion, cooling limits, and manual pressure advance.

## Implementation Acceptance Tests

3MF structure tests:

- Build a minimal fixture 3MF and assert the required archive members exist.
- Parse `3D/3dmodel.model` and assert Bambu namespace, `Application` prefix,
  `BambuStudio:3mfVersion`, unit, object UUID, build UUID, and build item
  transform.
- Parse `Metadata/project_settings.config` and assert the top-level header is
  exactly project-shaped: `name=project_settings`, `from=project`, semver
  version.
- Assert project settings include filament, process, printer IDs, machine model,
  variant, nozzle diameter, and printable height.

Inheritance tests:

- Resolve the filament, process, and machine chains above from fixture files.
- Assert child-over-parent merge behavior on an overridden key.
- Assert cycles fail with a clear error.
- Assert flattened project settings omit profile-only keys.
- Assert standalone user preset output keeps `from: User`, `inherits`, `type`,
  and no `setting_id`.

Enum tests:

- Assert `support_style=snug` passes and `support_style=organic` fails before
  bundle creation.
- Assert `support_type=normal(auto)` is validated separately from
  `support_style`.
- Feed a slicer log containing `substituted` or `old_value/new_value` and assert
  the slice gate fails unless allowlisted.

Delta normalization tests:

- Assert scalar, singleton array, and duplicated same-value array compare equal.
- Assert numeric string formatting compares equal.
- Assert percentage formatting compares as percentage values.
- Assert `nil` remains distinct from `"0"` and empty string.
- Assert the emitted settings report separates behavior deltas from metadata and
  normalization noise.

macOS profile path tests:

- Given both `user/default` and `user/1676299444`, choose the numeric cloud
  directory.
- Given only `user/default`, choose default.
- Dry-run install should show filament/process destinations without writing.
- Installer should refuse to proceed when a Bambu Studio process is running.

Transform and slice tests:

- Assert generated mesh vertices remain local/origin-centered after orientation
  and scale; bed placement belongs in 3MF placement metadata.
- Assert the part matrix and build-item transform agree for the selected bed.
- Run Bambu CLI against the bundled 3MF and fail on errors, enum substitutions,
  off-bed warnings, non-manifold warnings, or floating-cantilever warnings unless
  a bounded retry strategy handles them.
- Keep the slipper final bundle as a dogfood regression: it must open as native,
  keep custom profiles selected, place the object fully on the P2S plate, and
  slice with no blocker warnings.
