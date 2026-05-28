# Wave 131 - Trusted-User Final Readiness Handoff Files

Status: complete for UI/plan visibility. This is not trusted-user evidence.

## Problem

Wave 116 created trusted-user review handoff sheets that include the run report,
bundle, review instructions, proof boundary, and later `record-beta-feedback`
command. Later final-readiness work made physical validation rows very
self-contained, but trusted-user beta rows still mostly showed a start command
and handoff path. The report and `.3mf` bundle were available on disk but not
carried through the beta plan or web checklist row.

## Change

- `beta-feedback-plan` now discovers existing trusted-user handoff sheets and
  attaches the matching run report and Bambu `.3mf` bundle paths.
- The terminal trusted-user feedback plan renders `report:` and `bundle:` lines
  when those files exist.
- The final-readiness web view model now preserves `report_path`.
- The final-readiness web checklist renders row-level Report links.
- Trusted-user beta rows can render the later `record-beta-feedback` command as
  `Record after review`, while physical validation keeps `Record after print`.

## Verification

- `tests/test_beta_feedback.py::test_trusted_user_feedback_plan_surfaces_handoff_report_and_bundle_paths`
- `tests/test_final_readiness_web.py::test_build_final_readiness_view_keeps_trusted_user_supporting_paths_and_record_command`
- `tests/test_final_readiness_web.py::test_render_final_readiness_panel_labels_trusted_user_record_command_after_review`
- `tests/test_beta_feedback.py tests/test_final_readiness_web.py tests/test_final_plan.py tests/test_web_server.py`

## Boundary

This wave improves handoff visibility only. A trusted-user handoff, report,
bundle, and record command do not count as feedback. The beta gate still
requires three unique trusted users with completed `passed`, `failed`, or
`partial` packets and supporting evidence.
