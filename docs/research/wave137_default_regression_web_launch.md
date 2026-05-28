# Wave 137 - Default Regression-Aware Web Launch

Date: 2026-05-28

## Problem

Wave 136 fixed the terminal readiness command, but a plain local web launch still needed:

```bash
--regression-manifest regressions/dogfood_failures.json
```

Without that flag, the browser-visible readiness panels could drift from the now-correct default terminal readiness view.

## Change

`printpipe serve` now auto-discovers the standard dogfood regression manifest when it exists:

```bash
regressions/dogfood_failures.json
```

Explicit manifest paths still override the default. Parser construction remains lightweight and does not import the web server.

## Verification

Targeted red/green coverage:

```bash
.venv/bin/pytest tests/test_cli_serve.py tests/test_cli_readiness.py -q
```

The default server launch now passes the discovered manifest path into `printpipe.web.server.serve()`, which keeps the home page and JSON endpoints regression-aware.

## Boundary

This is local web launch parity only. It does not close the physical validation, trusted-user beta, or signed-distribution gates.
