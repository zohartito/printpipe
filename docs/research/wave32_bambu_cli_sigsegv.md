# Wave 32 Bambu CLI SIGSEGV Boundary

Status: superseded by Wave 36. This wave narrowed the crash; Wave 36 then
found the supported non-crashing PrintPipe path by embedding fully resolved
Bambu project settings in generated `.3mf` bundles.

## Current Host Facts

- Bambu Studio executable:
  `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`
- Bambu Studio version: `02.06.00.51`
- macOS version: `26.5`
- macOS build: `25F71`
- Known crash signal: signal 11, `SIGSEGV`
- Pasted crash stack signature:
  `Slic3r::DynamicPrintConfig::update_values_to_printer_extruders_for_multiple_filaments`
  after `Slic3r::Print::update_filament_maps_to_config`

## What This Means

The original failure was treated as a Bambu Studio CLI/runtime crash, not as
proof that the PrintPipe `.3mf` bundle was invalid. Later investigation split
the behavior into three cases:

- Raw direct STL passed to `BambuStudio --slice` can still crash or fail because
  it lacks Bambu project filament/profile context.
- Sparse PrintPipe `.3mf` bundles avoided the direct-STL path but still missed
  full machine/process/filament settings.
- Full-settings Bambu-native PrintPipe `.3mf` bundles slice successfully on this
  host.

The supported PrintPipe slice path is therefore: generate Bambu-native `.3mf`,
embed the fully resolved profile stack in `Metadata/project_settings.config`,
then invoke Bambu CLI on the `.3mf`.

## Implemented Handling

- Negative subprocess return codes are decoded as signals.
- Signal 11 becomes `slicer terminated by signal 11 (SIGSEGV)`.
- Slice receipts now include a `diagnosis` object with:
  - `kind`
  - `signal`
  - `scope`
  - `signature`
  - `printpipe_bundle_specific`
  - `evidence`
  - `recommended_next_step`
- Known crash-report text containing
  `update_values_to_printer_extruders_for_multiple_filaments` is classified as
  `extruder_filament_mapping`.

## Current Workaround

Use PrintPipe-generated `.3mf` bundles with fully resolved project settings for
CLI slicing. Do not use direct raw-STL CLI slicing as the product path.

## Wave 36 Resolution

- Old known-good slipper `.3mf`: Bambu CLI returned 0.
- Direct tiny STL: Bambu CLI still crashed/failed with missing filament context.
- Sparse PrintPipe slipper `.3mf`: Bambu CLI failed because there was "Nothing
  to be sliced" or incomplete project context.
- Patched full-settings PrintPipe `.3mf`: Bambu CLI returned 0.
- Fresh PrintPipe SUNLU TPU 90A test run: Bambu CLI returned 0, wrote
  `plate_1.gcode`, reported 207 s, 0.34 g, 48 layers, and zero warnings/errors.
