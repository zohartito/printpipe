Wave 192 - Tested Media Command Browser Handoff

Question: if a one-off semantic media smoke succeeded and final-next wants to promote that exact command into project config, does the action also point back to the local browser setup panel?

Finding: not before this wave. The blank provider setup action and configured-provider/no-smoke action both carried `browser_path: /#media-meshgen-setup`, but the tested-command promotion action only carried terminal commands.

Change:
- Added regression coverage for `configure_tested_media_meshgen_provider` preserving a browser handoff.
- Added `browser_path: /#media-meshgen-setup`.
- Added the label `Promote tested media meshgen command in the local app`.

Boundary:
- This does not configure the provider automatically.
- It does not run smoke.
- It does not close the semantic media meshgen gate.
- It only keeps browser and terminal handoffs aligned once a real successful smoke receipt exists.

Verification:

```bash
.venv/bin/pytest tests/test_final_plan.py::test_media_meshgen_action_plan_configures_tested_smoke_command -q
```
