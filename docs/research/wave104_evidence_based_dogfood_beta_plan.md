# Wave 104 Evidence-Based Dogfood Beta Plan

Status: complete for software dogfood planning. This is not physical print proof.

## Finding

`printpipe beta-plan` still hardcoded the canonical dogfood matrix as `action_required` even after the repo had local evidence for the slipper software run and three non-slipper live-sliced fixture runs. That made the beta plan less trustworthy: it was correctly strict about physical validation and trusted-user feedback, but stale about software dogfood.

## Change

- Added a read-only dogfood software status scanner inside `build_beta_action_plan()`.
- The scanner looks for a slipper software run with clean report warnings, successful bundle and bundle validation, and a recorded flex coupon.
- The scanner looks for at least three distinct non-slipper categories with clean report warnings, successful bundle and bundle validation, and a successful Bambu slice receipt.
- The `run_beta_dogfood` action is now `ready` only when that matrix is present; otherwise it stays `action_required` with the current slipper/non-slipper count.

## Current Local Result

With the current ignored `runs/` evidence, beta-plan reports:

- dogfood matrix: ready
- physical validation: action required
- trusted-user beta: action required
- failure capture: ready
- regression replay: ready
- rule updates: ready

The overall beta plan remains `action_required` because physical print packets and trusted-user packets are still not recorded.

## Boundary

This wave does not mark beta complete. Software dogfood receipts are not PLA/PETG/TPU physical proof, and they are not trusted-user feedback.
