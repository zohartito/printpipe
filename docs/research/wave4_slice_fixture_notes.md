# Wave 4 Slice Fixture Notes

Wave 4 Agent D adds the first compact real-world slipper slice fixture. The goal
is to preserve the acceptance-boundary numbers from the slipper proof without
committing the 46 MB G-code or a full Bambu run folder.

## Source Artifacts

- `/Users/zohartito/Desktop/slipper_3d/output/v3_cli_slice/slice_estimate.json`
  is the main source for the parsed CLI estimate: 21h 30m 16s, 77,416 seconds,
  195.73 g, $3.91 at $20/kg, and 425 layers.
- `/Users/zohartito/Desktop/slipper_3d/output/v3_cli_slice/result.json` records
  the Bambu CLI result: `return_code: 0`, `error_string: Success.`, empty
  `warning_message`, `total_predication: 77416.328125`, and
  `total_used_g: 195.72573852539063`.
- `/Users/zohartito/Desktop/slipper_3d/output/v3_cli_slice/slice_cli.log`
  confirms Bambu Studio CLI 02.06.00.51 and shows the raw CLI log was small, but
  the compact fixture keeps only summary facts needed by the parser.
- `/Users/zohartito/Desktop/slipper_3d/output/SLICE_ESTIMATE.md`,
  `/Users/zohartito/Desktop/slipper_3d/docs/real_world_results.md`, and the
  README cross-check the GUI result at about 21h37 and 195.6 g.

## Fixture Shape

- `tests/fixtures/bambu/slice_logs/slipper_v3_summary.log` is a short text
  summary using Bambu G-code header-style estimate lines, plus source paths and
  the GUI cross-check.
- `tests/fixtures/bambu/slice_estimates/slipper_v3_expected.json` keeps the
  expected values out of the test body so future real slice fixtures can follow
  the same pattern.

## Why It Matters

The slipper proof established the slice estimate as the final software gate:
the artifact is only print-viable when Bambu accepts the repaired, supported,
Bambu-native 3MF and reports a clean estimate. This fixture protects that
contract with real numbers: roughly 21.5 hours, roughly 196 g TPU, 425 layers,
and no user-facing warning message. It also anchors future parser changes
against the historical v3 success without requiring heavyweight artifacts in
normal unit tests.
