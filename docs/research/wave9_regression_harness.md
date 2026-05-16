# Wave 9 Regression Harness Notes

Status: helper foundation complete; execution harness pending.

## What Landed

Wave 9 adds a stdlib-only beta regression manifest helper in
`src/printpipe/beta/regression.py`.

The helper can:

- represent regression cases and manifests as frozen dataclasses,
- seed a failure case from an existing run folder manifest,
- render argv commands deterministically with `shlex.join`,
- validate manifest JSON shape and duplicate case IDs,
- load and write schema-versioned JSON files.

## Manifest Fields

Each case records:

- `case_id`
- `source_run_id`
- `fixture_path`
- `command`
- `expected`
- `notes`

`expected` is intentionally small for the first foundation: `failure` for known
dogfood failures and `success` for fixed cases that should remain green.

## Verification

```text
.venv/bin/python -m pytest tests/test_beta_regression.py
5 passed
```

## Not Included

- No CLI entry point.
- No automatic case runner.
- No roadmap changes.
