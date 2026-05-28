# Wave 97 - Beta Action Plan in Local Web UI

Status: implemented.

## Problem

Wave 96 made the beta plan available from the CLI, but the local app home page
still required users to open readiness, release, physical, and beta commands
separately.

## Decision

Expose the beta action plan in the browser:

- `GET /beta-plan.json`
- `GET /beta-plan.json?regression_manifest=<path>`
- home-page `Beta action plan` panel
- service link that inherits `printpipe serve --regression-manifest <manifest>`

## Boundary

This is a read-only surfacing layer. It does not create beta failure packets,
record physical evidence, mutate rules, or mark Phase 16 complete.

## Verification

Focused web verification passed:

```bash
.venv/bin/pytest tests/test_web_server.py -k "beta_plan or configured_regression_manifest or launch_controls"
```

Result: 4 passed.
