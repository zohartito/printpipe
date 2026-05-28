# Wave 108 - Trusted-User Not-Run Gate Hardening

## Finding

`record-beta-feedback` supports `outcome=not_run`, which is useful for recording that a beta attempt did not happen. The status scanner was counting those packets as trusted-user beta completion because it only filtered by `tester_type=trusted_user`.

## Fix

- `build_trusted_user_feedback_status()` now counts only `passed`, `failed`, and `partial` trusted-user packets toward completed trusted-user beta.
- `not_run` trusted users remain visible in `not_run_trusted_users`.
- `trusted_user_packet_count` still counts all trusted-user packets for auditability.
- `completed_trusted_user_count` and `completed_trusted_user_packet_count` expose the completion boundary directly.

## Why It Matters

A `not_run` packet is evidence that outreach or scheduling happened, not evidence that the product was tested. Letting it close the beta gate would make the final readiness claim too soft.

## Verification

- `tests/test_beta_feedback.py`
- `tests/test_beta_plan.py`
- `tests/test_final_plan.py`
- `tests/test_web_server.py`
