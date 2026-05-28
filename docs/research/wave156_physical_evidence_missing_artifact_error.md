# Wave 156 - Physical Evidence Missing Artifact Error

## Question

Does `record-physical-evidence` tell the user which file is missing when a
placeholder `--photo` or `--artifact` path does not exist?

## Finding

The CLI checked the run root correctly, but then caught every
`FileNotFoundError` from artifact copying and re-raised it as if the run root was
missing. That made placeholder photo paths from physical plans confusing: the
run existed, but the error said it did not.

## Change

- Preserve the initial run-root existence check.
- When artifact copying raises `FileNotFoundError`, convert it to
  `photo/artifact file not found: <path>`.
- Keep parser behavior unchanged: the command still exits nonzero and writes the
  actionable error to stderr.

## Verification

```bash
.venv/bin/pytest \
  tests/test_beta_physical_evidence.py::test_cli_record_physical_evidence_reports_missing_photo_path -q
```

Result: `1 passed`.

## Boundary

This improves the operator error. It does not create physical evidence and does
not allow placeholder photo paths to satisfy physical validation.
