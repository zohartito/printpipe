# Wave 111 - Trusted-User Raw Packet Completeness Gate

## Finding

`record-beta-feedback` validates required fields, but the scanner also reads raw `90_beta/trusted_user_feedback.json` files from disk. A hand-written or damaged packet could say `tester_type=trusted_user` and `outcome=passed` while omitting required evidence fields such as `summary`.

## Fix

- Completed trusted-user beta now requires:
  - `outcome` in `passed`, `failed`, or `partial`
  - all required packet fields present
- `not_run` still stays audit-only.
- incomplete trusted-user packets are surfaced as:
  - `incomplete_trusted_user_packet_count`
  - `incomplete_trusted_user_packets`
- the terminal status renderer lists incomplete packets and missing fields.

## Boundary

This does not create tester feedback. It prevents incomplete raw packets from satisfying the trusted-user beta gate.

## Verification

- `tests/test_beta_feedback.py`
- `tests/test_beta_plan.py`
- `tests/test_beta_readiness.py`
- `tests/test_final_plan.py`
