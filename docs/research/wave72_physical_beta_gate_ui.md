# Wave 72 - Physical Beta Gate in Local UI

Date: 2026-05-28

## Why

Wave 71 added the physical validation scanner and CLI, but beta users looking at
the local app still had to know that command existed. The home page should show
the same real-world gate directly: which material families have credible passed
evidence, which are missing, and which are recorded but not passed.

## What changed

- The local web home page reads `build_physical_validation_status()` when
  `runs_dir` is configured.
- A `Physical beta gate` panel shows the overall status.
- PLA, PETG, and TPU cards show family status, passed count, packet count, and
  missing reason.
- The panel repeats the strict CLI command:
  `printpipe physical-status --runs-dir runs --strict`.

## Boundaries

- This panel is read-only.
- It does not record evidence.
- It does not edit `90_physical/physical_evidence.json`.
- It does not infer physical proof from `.3mf`, slice receipts, generated coupon
  artifacts, or photos outside the evidence packet.

## Verification

Focused red/green target:

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_physical_beta_gate_status
```

The test first failed because the home page did not contain a physical beta gate
panel, then passed after the web UI started rendering the scanner output.
