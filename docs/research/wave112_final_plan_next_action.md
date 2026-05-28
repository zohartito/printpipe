# Wave 112 - Final Readiness Command Center and Next-Action Contract

## Finding

`printpipe final-plan` correctly aggregated the remaining external gates, but the home page still spread the same truth across several panels. Agents and UI code also had to infer the first actionable step by scanning sections and action objects. That creates room for different surfaces to disagree about what Zohar should do first.

## Fix

- Added `src/printpipe/web/final_readiness.py` as a read-only view model and renderer for a home-page `Final readiness / Remaining actions` command center.
- The panel reads only existing plan/status payloads:
  - `build_final_action_plan()`
  - `build_physical_validation_status()`
  - `build_trusted_user_feedback_status()`
- The panel shows the three remaining pillars:
  - physical validation
  - trusted-user beta
  - release distribution
- The panel flattens remaining actions into one checklist while preserving proof boundaries.
- Added top-level `next_action` to the final-plan JSON contract.
- Added top-level `next_command` as the runnable command from that action.
- Preserved the existing section order:
  - physical validation
  - trusted-user beta
  - release distribution
- Preferred action-specific commands before section-level commands.
- Added a terminal `Next action` block to `render_final_action_plan()`.

## Boundary

This is orchestration metadata and UI visibility, not evidence. It does not satisfy physical validation, trusted-user beta, or signed distribution gates.
