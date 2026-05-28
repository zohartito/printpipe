# Wave 141 - Physical Print Status Placeholder Honesty

## Question

Can the physical-validation plan accidentally create fake-positive print evidence by giving the operator a copy-paste command that already says the print passed?

## Finding

Yes. Before this wave, `printpipe physical-plan --runs-dir runs --json` produced PLA, PETG, and TPU `record-physical-evidence` commands with `--print-status passed` baked in. That was inconsistent with the proof boundary: the plan was honest that digital artifacts are not physical proof, but its post-print command still preselected the best possible result.

## Change

`src/printpipe/beta/physical_plan.py` now emits:

```bash
--print-status "<passed|failed|partial>"
```

The command still carries the useful concrete context:

- real validation run folder
- printer label
- material label
- object label
- coupon print type
- material-specific observation prompts
- photo placeholder

The only thing it no longer guesses is the physical outcome.

## Verification

Targeted red/green test:

```bash
.venv/bin/pytest tests/test_beta_physical_plan.py -q
```

Result after implementation:

```text
12 passed
```

Live plan spot-check:

```bash
.venv/bin/printpipe physical-plan --runs-dir runs --json
```

The PLA, PETG, and TPU actions now contain `--print-status "<passed|failed|partial>"` and do not contain `--print-status passed`.

## Boundary

This is an honesty improvement, not physical validation. The physical gate remains open until real coupons are printed, observed, photographed, and recorded with an explicit outcome.
