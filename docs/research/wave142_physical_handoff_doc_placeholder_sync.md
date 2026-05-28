# Wave 142 - Physical Handoff and Doc Placeholder Sync

## Question

After Wave 141 fixed generated physical-plan commands, were there still stale places telling the operator to record `--print-status passed` before real evidence exists?

## Finding

Yes. The current physical plan and future `physical-start` output were fixed, but stale generated Markdown and beta docs still showed copy-pasteable passing commands:

- `runs/physical-pla-validation/90_physical/physical_print_handoff.md`
- `runs/physical-petg-validation/90_physical/physical_print_handoff.md`
- `runs/physical-tpu-validation/90_physical/physical_print_handoff.md`
- `docs/beta/onboarding.md`
- `docs/beta/slipper_dogfood.md`

The run handoff files are local artifacts rather than tracked Git files, but they are exactly what an operator would open on print day.

## Change

The beta docs now show:

```bash
--print-status "<passed|failed|partial>"
```

The text says to replace the placeholder with the observed result after printing. The existing local PLA, PETG, and TPU handoff sheets were also refreshed to match the current plan output.

## Tests

Added doc guardrails:

- `tests/test_beta_onboarding_docs.py`
- `tests/test_beta_slipper_dogfood_doc.py`

They require the placeholder command and reject `--print-status passed` in the beta guides.

Targeted verification:

```bash
.venv/bin/pytest tests/test_beta_onboarding_docs.py tests/test_beta_slipper_dogfood_doc.py tests/test_beta_physical_plan.py -q
```

Result:

```text
20 passed
```

## Boundary

This sync removes stale unsafe instructions. It still does not validate any material family physically. The physical gate remains open until real printed coupons are recorded with explicit outcomes, observations, and photos.
