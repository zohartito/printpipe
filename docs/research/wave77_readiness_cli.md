# Wave 77 - Readiness CLI Command

## Goal

Expose the combined beta/release readiness report from the terminal so release scripts and agents do not need to scrape the local web UI or call the JSON endpoint manually.

## What Changed

- Added `printpipe readiness --runs-dir runs`.
- Added `printpipe readiness --json` for structured automation output.
- Added `printpipe readiness --strict`, which returns exit code `2` unless the combined report is `ready`.
- Added `render_beta_readiness_report()` for concise human terminal output.

## Verification Scope

- Parser accepts `readiness`, `--runs-dir`, `--json`, and `--strict`.
- Strict JSON mode returns non-zero when readiness is `action_required`.
- Human mode prints the overall status and each gate summary.

## Boundary

This is a read-only gate. It does not complete physical PLA/PETG/TPU print evidence, install local dependencies, configure Bambu Studio, or sign/notarize release artifacts.
