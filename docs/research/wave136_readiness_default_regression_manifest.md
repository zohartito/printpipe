# Wave 136 - Default Regression-Aware Readiness

Date: 2026-05-28

## Problem

`printpipe readiness --runs-dir runs --strict` was locally misleading in the mature PrintPipe repo because it ignored the standard dogfood regression manifest unless the caller remembered to pass:

```bash
--regression-manifest regressions/dogfood_failures.json
```

That made the default terminal gate report one extra action-required item even though the canonical manifest exists and already passes.

## Change

The CLI now auto-discovers `regressions/dogfood_failures.json` for `printpipe readiness` when no explicit manifest path is provided.

Explicit paths still win:

```bash
printpipe readiness --runs-dir runs --regression-manifest custom.json --strict
```

Fresh repos or repos without the standard manifest keep the existing optional behavior; the beta regression gate remains not applicable unless a manifest is provided.

## Verification

Targeted red/green coverage:

```bash
.venv/bin/pytest tests/test_cli_readiness.py -q
```

Local smoke:

```bash
.venv/bin/printpipe readiness --runs-dir runs --strict
```

Current local result is still action-required, but for the correct external gates only:

- physical validation
- trusted-user beta
- release signing

Failure regression coverage and beta regression replay are ready by default.

## Boundary

This is readiness-reporting friction removal. It does not create physical coupon evidence, trusted-user feedback packets, Developer ID/notary credentials, or a signed Windows installer.
