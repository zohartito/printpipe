# Wave 32 Bambu CLI SIGSEGV Boundary

Status: F13 is narrowed but not solved. PrintPipe now classifies Bambu CLI
process crashes as a slicer/runtime boundary and preserves that diagnosis in
slice receipts.

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

The failure is currently treated as a Bambu Studio CLI/runtime crash, not as
proof that the PrintPipe `.3mf` bundle is invalid. The important evidence is
that the same local Bambu CLI path has crashed on both a direct tiny STL and a
PrintPipe-generated `.3mf`.

PrintPipe still cannot call a run fully slice-verified until the CLI returns a
successful receipt or an equivalent trusted workaround is built.

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

Use Bambu Studio GUI/manual slicing for real print decisions. Re-test CLI
slicing after a Bambu Studio update, a macOS update, or a discovered
non-crashing CLI invocation.

## Remaining F13 Work

- Capture a fresh crash receipt from this machine without relying on a pasted
  Apple crash dialog.
- Test a different Bambu Studio version or macOS version.
- Test a Windows Bambu Studio CLI path.
- Try a non-P2S profile and a one-filament generic profile to determine whether
  the crash is tied to P2S/profile/extruder map handling.
- If a non-crashing invocation is found, record it as the default slice-gate
  command and move F13 to done.
