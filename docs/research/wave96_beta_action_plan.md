# Wave 96 - Beta Action Plan

Status: implemented.

## Problem

Phase 16 had several honest partials: dogfood, trusted-user beta, failed-run
collection, regression promotion, and rule updates. Previous waves added the
pieces, but there was no single command that converted the remaining beta work
into a sequenced action list.

## Decision

Add a read-only beta planner:

```bash
printpipe beta-plan --runs-dir runs
printpipe beta-plan --runs-dir runs --regression-manifest regressions/beta_regressions.json --json
```

The planner reads only evidence already on disk:

- `90_beta/failure_report.json` packets
- physical validation status from `runs/`
- optional beta regression manifest execution status

It does not record evidence, mutate rules, or mark beta complete.

## Outputs

The plan reports:

- dogfood matrix action
- physical validation action via `printpipe physical-plan`
- beta failure capture skeleton via `printpipe record-beta-failure`
- regression replay via `printpipe run-regressions`
- trusted-user beta action
- material/orientation/repair rule triage action

## Boundary

A generated beta plan is not trusted-user evidence, physical print proof, or a
material/orientation/repair rule update until those results are recorded.

## Verification

Focused verification passed:

```bash
.venv/bin/pytest tests/test_beta_plan.py
```

Result: 4 passed.
