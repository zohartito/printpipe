# Wave 157 - Rule Update Gate Requires Failure Triage

## Question

Can captured beta/dogfood failures exist while the rule-update gate reports
`not_applicable` because no rule-update packets have been recorded?

## Finding

Yes. The failure-regression gate already knew captured failures existed, but the
rule-update gate only looked at rule-update packets. With failures present and no
rule packets, it reported `not_applicable`, which could make release planning
treat untriaged failures as irrelevant.

## Change

- Pass failure-regression status into the rule-update gate.
- If one or more captured failures exist and rule-update packets are missing,
  `rule_updates` now reports `action_required`.
- If no captured failures exist and no rule packets exist, the gate remains
  `not_applicable`.

## Verification

```bash
.venv/bin/pytest \
  tests/test_beta_readiness.py::test_beta_readiness_report_blocks_rule_updates_when_failures_have_no_packets -q
```

Result: `1 passed`.

## Boundary

This does not fabricate rule-update evidence. It only makes the triage debt
visible until a verified material, orientation, or repair rule-update packet is
recorded.
