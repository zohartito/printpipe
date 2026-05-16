# Wave 9 Integration Summary

Status: complete as beta/regression infrastructure; physical and outside-user beta remain pending.

## What Landed

Wave 9 added the beta operating layer:

- Slipper dogfood validation gates with explicit software and physical pass/fail criteria.
- Non-slipper beta run plan for figurine, cup/vase, flat bracket, decorative organic, and existing STL fixtures.
- Structured beta failure report helpers and a Markdown failure template.
- Regression manifest helpers for turning failed runs into repeatable test cases.
- GitHub issue templates for failed runs and beta feedback.
- Beta onboarding docs for 3-5 trusted users.

## What Is Still Partial

- The slipper has not been physically printed from a PrintPipe-generated bundle.
- The non-slipper beta plan is documented, but the objects have not been physically printed by beta users.
- No outside beta users have run the app yet.
- Regression manifest helpers exist, but there is not yet a CLI runner for manifest cases.
- Material, orientation, and repair rules will only be updated after real beta failures produce evidence.

## Verification

```text
.venv/bin/python -m pytest
201 passed, 2 skipped
```
