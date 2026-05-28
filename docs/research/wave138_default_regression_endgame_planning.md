# Wave 138 - Default Regression-Aware Endgame Planning

Date: 2026-05-28

## Problem

After Waves 136 and 137, readiness and the local web server defaulted to the standard dogfood regression manifest, but several terminal planning commands still needed an explicit flag:

```bash
--regression-manifest regressions/dogfood_failures.json
```

That left `final-plan` reporting an empty `regression_manifest_path` even in the mature repo where the canonical manifest exists.

## Change

The following commands now auto-discover `regressions/dogfood_failures.json` when no explicit manifest is provided:

- `printpipe beta-plan`
- `printpipe release-status`
- `printpipe release-plan`
- `printpipe release-start`
- `printpipe final-plan`
- `printpipe final-next`

Explicit manifest paths still override the default. Repos without the standard manifest keep the existing optional behavior.

## Verification

Targeted red/green coverage:

```bash
.venv/bin/pytest \
  tests/test_final_plan.py::test_cli_final_plan_uses_standard_regression_manifest_when_present \
  tests/test_final_plan.py::test_cli_final_next_uses_standard_regression_manifest_when_present \
  tests/test_beta_plan.py::test_cli_beta_plan_uses_standard_regression_manifest_when_present \
  tests/test_release_status.py::test_cli_release_status_uses_standard_regression_manifest_when_present \
  tests/test_release_status.py::test_cli_release_plan_uses_standard_regression_manifest_when_present \
  tests/test_release_status.py::test_cli_release_start_uses_standard_regression_manifest_when_present \
  -q
```

Local smoke:

```bash
.venv/bin/printpipe final-plan --release-dir dist/release --runs-dir runs --json
.venv/bin/printpipe beta-plan --runs-dir runs --json
```

The default `final-plan` JSON now includes the canonical regression manifest path, and `beta-plan` renders the dogfood regression replay action as ready.

## Boundary

This is terminal planning truth only. It does not close the physical validation, trusted-user beta, or signed-distribution gates.
