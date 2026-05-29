# Wave 178 - Media Heightfield Honesty Gate

Question: should the built-in `media-meshgen-heightfield` adapter close the image/GIF/video meshgen readiness gate?

Finding: no. The adapter is useful because it proves local media plumbing with a real STL output, but it does not perform semantic 3D reconstruction from a reference. Counting it as a live media meshgen provider made readiness look stronger than the product evidence.

Change:

- `build_media_meshgen_readiness()` now marks `media-meshgen-heightfield` as `plumbing_only`.
- Plumbing-only adapters no longer increment `live_media_provider_count`.
- Readiness and final-plan stay `action_required` when heightfield is the only configured media command.
- Final-plan no longer recommends turning a heightfield smoke receipt into the configured semantic provider.
- `media-meshgen-smoke` now records the resolved project-config command in `20_meshgen/smoke.json`.

Proof boundary:

- Heightfield smoke proves adapter protocol, media input prep, subprocess execution, receipt writing, and downstream mesh plumbing.
- It does not prove semantic image/GIF/video-to-object reconstruction quality.

Focused verification:

```bash
.venv/bin/pytest tests/test_meshgen.py::test_media_meshgen_readiness_treats_builtin_heightfield_as_plumbing_only tests/test_final_plan.py::test_media_meshgen_action_plan_configures_tested_smoke_command tests/test_final_plan.py::test_media_meshgen_action_plan_does_not_promote_builtin_heightfield_smoke tests/test_cli_media_meshgen_smoke.py::test_media_meshgen_smoke_records_project_config_command -q
```

Result: 4 passed.
