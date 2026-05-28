# Wave 154 - Media Meshgen Readiness Gate

## Question

Can PrintPipe warn upfront when image/GIF/video-to-mesh generation is unavailable,
instead of only failing after a media run reaches the `meshgen` stage?

## Finding

The runtime path already failed honestly with a `provider_unavailable` meshgen
receipt when `PRINTPIPE_HUNYUAN3D_COMMAND` was unset. The missing piece was
readiness: `doctor`, `readiness`, and the local web readiness panels did not
surface the provider gap before a user started a media or prompt-based run.

## Change

- Added a media-meshgen provider readiness rollup.
- The rollup health-checks the configured Hunyuan3D adapter and placeholder
  hosted providers, then counts live image/GIF/video-capable providers.
- `printpipe doctor` now includes `meshgen.overall_status` and the live provider
  count.
- `printpipe readiness` now includes a `media_meshgen` gate.
- When no live provider exists, the gate is `action_required` and points at
  `PRINTPIPE_HUNYUAN3D_COMMAND` or hosted provider configuration.

## Verification

```bash
.venv/bin/pytest \
  tests/test_beta_readiness.py::test_beta_readiness_report_blocks_when_media_meshgen_provider_unavailable \
  tests/test_env_doctor.py::test_environment_report_combines_dependencies_bambu_and_profile_detection -q
```

Result: `2 passed`.

## Boundary

This is an upfront signal, not a provider installation. Existing mesh inputs stay
usable without a media provider. Image/GIF/video/prompt-to-mesh runs still need a
configured Hunyuan3D command or a future hosted provider.
