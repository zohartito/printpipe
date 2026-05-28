# Wave 86 - Physical Validation Action Plan

## Context

The remaining beta gate is physical, not digital: PrintPipe still needs one credible PLA, one PETG, and one TPU coupon or small-object print recorded with photos and material-specific observations. Earlier waves added evidence packet writing, status scanning, run-detail surfacing, readiness gates, and release gates, but the CLI only said what was missing.

## Change

- Added `printpipe.beta.physical_plan.build_physical_validation_plan()`.
- Added `printpipe physical-plan --runs-dir runs`.
- Added JSON and human renderers.
- For each missing or incomplete material family, the plan emits:
  - current family status,
  - reason,
  - required fields,
  - target run root,
  - material/object hints,
  - an exact `printpipe record-physical-evidence ...` command skeleton.
- The command targets an existing incomplete packet's run folder when one is available, otherwise it uses a placeholder run root for the next real physical print.

## Boundary

This is an action planner only. Generated coupons, digital artifacts, Bambu slice receipts, and command skeletons do not count as physical proof until Zohar actually prints the material sample and records evidence with a photo/artifact packet.

## Verification

```bash
.venv/bin/pytest tests/test_beta_physical_plan.py
.venv/bin/pytest tests/test_beta_physical_plan.py tests/test_beta_physical_status.py tests/test_beta_physical_evidence.py tests/test_beta_readiness.py tests/test_cli_readiness.py tests/test_release_status.py
```
