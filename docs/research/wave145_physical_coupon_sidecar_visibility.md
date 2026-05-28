# Wave 145 - Physical Coupon Sidecar Visibility

## Question

Do final-readiness checklist rows expose the same physical coupon artifacts that the final-plan contract already carries?

## Finding

The final action plan and next-action callout already preserved both:

- `coupon_stl_path`
- `coupon_json_path`

The checklist row renderer only showed the STL row. That contradicted the Wave 119/134 documentation that claimed action rows expose supporting artifact and sidecar paths.

## Change

- Added regression coverage for physical coupon JSON sidecar preservation and rendering.
- Updated the final-readiness checklist row renderer to show `Coupon sidecar`.
- Routed coupon STL and JSON rows through the existing safe run-artifact link helper.

## Verification

```bash
.venv/bin/pytest \
  tests/test_final_readiness_web.py::test_build_final_readiness_view_flattens_section_actions \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_includes_honest_boundaries \
  tests/test_final_readiness_web.py::test_render_final_readiness_panel_links_run_artifact_paths -q
```

Result: `3 passed`.

## Boundary

This wave improves artifact visibility only. A visible coupon sidecar is still digital evidence, not physical print proof. The physical validation gate remains open until PLA, PETG, and TPU coupons are printed, observed, photographed, and recorded with explicit outcomes.
