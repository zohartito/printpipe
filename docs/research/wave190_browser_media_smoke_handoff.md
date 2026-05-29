# Wave 190 - Browser-Aware Media Smoke Handoff

Question: after a media provider is configured but no successful smoke receipt exists, does final-next point to the browser smoke form as well as the terminal command?

Finding: not before this wave. The configure-provider state had a browser path, but the provider-ready/no-smoke state only exposed terminal smoke commands.

What changed:

- The `media_meshgen_smoke` final-plan action now carries `browser_path: /#media-meshgen-setup`.
- It carries `browser_label: Run media meshgen smoke in the local app`.
- Final-next preserves those fields automatically through the existing action payload.

Truth boundary:

- This is a handoff improvement only.
- It does not configure a real provider.
- It does not run the smoke test.
- The media gate remains action-required until a successful smoke receipt exists.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_final_plan.py::test_media_meshgen_action_plan_requires_smoke_when_provider_is_ready \
  tests/test_final_plan.py::test_media_meshgen_action_plan_requires_provider_before_smoke \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_labels_media_meshgen_setup_flow \
  -q
```
