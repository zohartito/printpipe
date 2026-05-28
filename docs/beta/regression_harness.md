# Beta Regression Harness Foundation

Status: failure-intake ready. The CLI can now append cases while recording beta
failure packets, but there is still no automatic manifest runner.

## Purpose

The beta regression manifest records dogfood failures as repeatable cases. A
failed run can be converted into a small JSON entry that names the source run,
the fixture to replay, the command shape that should be exercised, the expected
outcome, and notes that explain why the case exists.

The helper lives in `src/printpipe/beta/regression.py` and uses only the Python
standard library.

## Manifest Shape

```json
{
  "schema_version": 1,
  "cases": [
    {
      "case_id": "slipper-non-manifold",
      "source_run_id": "20260516-101112-slipper",
      "fixture_path": "tests/fixtures/regression/slipper.stl",
      "command": ["printpipe", "run", "tests/fixtures/regression/slipper.stl"],
      "expected": "failure",
      "notes": "Captured from a failed dogfood run."
    }
  ]
}
```

`expected` is one of:

- `failure`: the case preserves a known failing path until the bug is fixed.
- `success`: the case should now pass and should guard against regression.

Commands are stored as argv lists, not shell strings. Use `render_command()` for
stable display text when writing reports or debugging a manifest entry.

## Helpers

- `RegressionCase`: immutable case record with `rendered_command`.
- `RegressionManifest`: immutable manifest record with schema version 1.
- `case_from_run(run_root, command=...)`: seeds a case from a run folder's
  `manifest.json`, defaulting to `expected="failure"` and the run's stored input
  as the fixture path.
- `validate_regression_manifest(payload)`: returns a tuple of validation errors.
- `load_regression_manifest(path)`: reads and validates JSON, returning a
  `RegressionManifest`.
- `write_regression_manifest(manifest, path)`: validates and writes indented JSON
  with a trailing newline.
- `render_command(command)`: renders argv with `shlex.join` for deterministic,
  shell-safe display.

## Intended Flow

1. Capture a failing beta run.
2. Move or copy the relevant input artifact into a durable fixture location.
3. Run `printpipe record-beta-failure ... --regression-manifest ...` to write
   `90_beta/failure_report.json`, `90_beta/failure_report.md`, copy attached
   artifacts into `90_beta/artifacts/`, and append a manifest case.
4. Or create a case directly with `case_from_run(...)`, passing the replay
   command and notes, then write or update a manifest with
   `write_regression_manifest(...)`.
5. Future harness work can load the manifest and decide whether each case should
   currently fail or succeed.

Example:

```bash
printpipe record-beta-failure runs/<run-id> \
  --input-type existing_stl \
  --material "SUNLU TPU 90A" \
  --printer "Bambu Lab P2S" \
  --failed-stage slice \
  --symptom "Bambu reported a floating cantilever warning" \
  --artifact "Slice log|slice_log|70_slice/slice.log|CLI stderr" \
  --reproduction-command "printpipe run 00_input/input.stl --material tpu" \
  --physical-print-status not_printed \
  --regression-manifest tests/fixtures/regression/failure_manifest.json
```

## Current Limits

- There is no runner that executes manifest cases.
- Validation checks schema shape and stable fields, but it does not require
  fixture files to exist because manifests may be authored before fixtures are
  copied into place.
