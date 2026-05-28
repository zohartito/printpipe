# Wave 109 - Trusted-User Not-Run Visibility

## What Changed

- Terminal trusted-feedback status now lists `Not-run trusted users` when present.
- The local web dashboard now shows a `Not-run testers` card in the trusted-user feedback panel.
- The web copy explicitly says not-run packets are audit records, not completed beta feedback.

## Why

Wave 108 fixed the gate semantics in JSON, but a human reviewing the CLI or dashboard still needed to see which testers had `not_run` packets. Otherwise a coordinator could lose track of outreach attempts while the gate correctly remains incomplete.

## Boundary

`not_run` remains excluded from completed trusted-user beta. Failed and partial feedback still count because those represent completed reviews.

## Verification

- `tests/test_beta_feedback.py`
- `tests/test_web_server.py`
