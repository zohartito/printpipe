# Wave 158 - No-Op Preprocessing Receipts Are Skipped

## Question

Do background-removal and lighting-normalization receipts claim success when no
configured command actually ran?

## Finding

Yes. The no-command branches copied frames forward and correctly recorded
metadata such as `semantic_background_removed=false`, but the receipts still used
`succeeded`. That made reports read as if preprocessing ran successfully when it
was only an honest no-op copy.

## Change

- No-command background removal now returns `StageStatus.SKIPPED`.
- No-command lighting normalization now returns `StageStatus.SKIPPED`.
- Configured command paths still return `StageStatus.SUCCEEDED`.

## Verification

```bash
.venv/bin/pytest \
  tests/test_inputs.py::test_prepare_still_image_saves_extracted_cleaned_selected_reference_and_manifest \
  tests/test_inputs.py::test_prepare_gif_and_video_extract_with_fake_runner_and_select_references \
  tests/test_inputs.py::test_clean_references_runs_configured_background_and_lighting_commands -q
```

Result: `3 passed`.

## Boundary

This is receipt honesty only. It does not add semantic background removal or
lighting normalization; those still require configured commands.
