# Wave 75 - Combined Beta Readiness Report

Date: 2026-05-28

## Why

The local app could expose physical validation and environment doctor status
separately, but the product still needed one direct answer to: what blocks final
beta/release readiness right now?

This wave adds a combined report while keeping the hard boundary intact:
reporting a gate is not the same as completing it.

## What changed

- Added `printpipe.beta.readiness.build_beta_readiness_report()`.
- Added readiness gates for:
  - physical validation
  - required dependencies
  - filesystem access
  - Bambu Studio
  - Bambu profile folders
  - release signing
- Added `GET /readiness.json`.
- Added a home page service link for `Readiness JSON`.

## Boundaries

- The report is read-only.
- It does not print PLA/PETG/TPU coupons.
- It does not install missing dependencies or signing certificates.
- It does not sign or notarize releases.
- It does not install Bambu Studio or create Bambu profile folders.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest \
  tests/test_beta_readiness.py \
  tests/test_web_server.py::test_readiness_json_endpoint_returns_combined_gate_report
```

The readiness tests first failed because `printpipe.beta.readiness` did not
exist. The web endpoint test then failed because `build_beta_readiness_report`
was not exposed from the local web layer. Both passed after implementation.
