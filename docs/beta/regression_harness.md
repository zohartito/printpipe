# Beta Regression Harness Foundation

Status: foundation only. This does not add a CLI command or automatic runner.

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
3. Create a case with `case_from_run(...)`, passing the replay command and notes.
4. Write or update a manifest with `write_regression_manifest(...)`.
5. Future harness work can load the manifest and decide whether each case should
   currently fail or succeed.

## Current Limits

- There is no CLI integration.
- There is no runner that executes manifest cases.
- Validation checks schema shape and stable fields, but it does not require
  fixture files to exist because manifests may be authored before fixtures are
  copied into place.
