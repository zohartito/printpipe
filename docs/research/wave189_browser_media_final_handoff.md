# Wave 189 - Browser-Aware Media Final Handoff

Question: after adding the browser media setup workflow, does the final next-action handoff point users and agents at that browser setup surface?

Finding: not before this wave. Final-next had terminal commands for adapter template creation, smoke, and smoke-status, but no structured browser path to the media setup panel.

What changed:

- `configure_media_meshgen_provider` now carries `browser_path: /#media-meshgen-setup`.
- The action also carries a human `browser_label`.
- Final-next payloads preserve those fields.
- The final-readiness panel renders a `Browser setup` link beside the existing terminal commands.

Truth boundary:

- This is a handoff/UX improvement only.
- It does not configure a semantic provider.
- It does not run ComfyUI.
- It does not create a successful smoke receipt.
- The media gate remains action-required until real provider smoke evidence exists.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_final_plan.py::test_media_meshgen_action_plan_requires_provider_before_smoke \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_labels_media_meshgen_setup_flow \
  -q
```
