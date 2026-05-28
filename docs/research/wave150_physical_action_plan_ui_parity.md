# Wave 150 - Physical Action Plan UI Parity

## Question

Does the dedicated physical action-plan panel show the print-day context, artifacts, and commands needed to execute a validation coupon?

## Finding

`physical-plan` already exposed rich action metadata once a starter packet existed:

- material and object context
- coupon STL and JSON sidecar
- Bambu `.3mf` bundle and validation receipt
- optional slice receipt or slice command
- physical print handoff Markdown
- open-folder print-handoff command
- post-print evidence recording command

The home-page `Physical action plan` panel showed required fields and commands, but hid most of those files and the physical context. Final-readiness could show them, so the dedicated physical panel lagged behind the endgame checklist.

## Change

- Render `Physical context` on physical action cards.
- Include material, object label, print type, and run folder.
- Render coupon, sidecar, bundle, bundle-validation, slice receipt, and handoff paths when present.
- Split setup, starter-packet, print-handoff, slice-if-needed, and `Record after print` commands.

## Verification

```bash
.venv/bin/pytest \
  tests/test_web_server.py::test_home_response_renders_started_physical_action_context_and_files \
  tests/test_web_server.py::test_home_response_renders_physical_action_plan -q
```

Result: `2 passed`.

## Boundary

This is execution UI only. It does not count generated coupons, bundles, or slice receipts as physical proof. PLA, PETG, and TPU validation still require real prints, photos, observations, and explicit evidence packets.
