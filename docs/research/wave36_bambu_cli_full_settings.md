# Wave 36 Bambu CLI Full-Settings Slice Gate

## Finding

Bambu Studio CLI slicing is reliable for PrintPipe when the generated `.3mf`
contains a fully resolved Bambu project profile stack. It is not reliable for
raw direct-STL CLI slicing, and sparse `.3mf` bundles can fail because the CLI
cannot infer enough printer/filament/process context.

## Evidence

- Old slipper repo `Slipper_TPU90A_P2S_v3_cli.3mf`: Bambu CLI returned 0.
- Direct tiny STL through Bambu CLI: still crashed or failed because no filament
  colors/project context were present.
- PrintPipe sparse `.3mf`: failed with "Nothing to be sliced" / missing full
  settings context.
- PrintPipe full-settings `.3mf`: returned 0 and wrote G-code.
- Fresh PrintPipe test command:

```bash
.venv/bin/printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl \
  --material "SUNLU TPU 90A" \
  --slice \
  --bambu-cli /Applications/BambuStudio.app/Contents/MacOS/BambuStudio
```

Result: `return_code=0`, no warnings/errors, `plate_1.gcode` written, 207 s,
0.34 g, 48 layers.

## Root Cause

The old working slipper `.3mf` embedded about 454 project settings, including
resolved machine keys such as `printable_area` and `machine_start_gcode`.
PrintPipe's earlier bundles embedded only the sparse custom TPU/process
overrides, so Bambu CLI had to rediscover full profiles by name and failed in
headless slicing.

## Fix

PrintPipe now loads Bambu/Orca profile roots, resolves inheritance for machine,
process, and filament profiles, embeds those full settings into
`Metadata/project_settings.config`, then applies material-specific overrides on
top. For SUNLU TPU 90A, the project settings keep the custom slipper profile IDs
while carrying the full Bambu P2S + TPU base context.

## Boundary

Direct raw-STL Bambu CLI slicing is still not treated as a product requirement.
The supported slice gate is PrintPipe `.3mf` -> Bambu CLI -> G-code receipt.
