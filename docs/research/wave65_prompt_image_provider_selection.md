# Wave 65 - Prompt Image Provider Selection

## Goal

Turn prompt-only reference image generation from a single raw command hook into a selectable provider layer.

## What Changed

- Added provider resolution for `auto`, `command`, and `openai`.
- Preserved `PRINTPIPE_PROMPT_IMAGE_COMMAND` as the custom/local command provider.
- Added a built-in OpenAI Images API adapter for prompt-only reference images.
- Added `printpipe run --prompt-image-provider auto|command|openai`.
- Added a local web `Prompt image provider` selector.
- Persisted the selected provider in web launch metadata.

## OpenAI Adapter

The OpenAI provider requires `OPENAI_API_KEY` and calls `/v1/images/generations`.

Configurable environment variables:

- `PRINTPIPE_OPENAI_IMAGE_MODEL` default `gpt-image-2`
- `PRINTPIPE_OPENAI_IMAGE_SIZE` default `1024x1024`
- `PRINTPIPE_OPENAI_IMAGE_QUALITY` default `low`
- `PRINTPIPE_OPENAI_IMAGE_BACKGROUND` default `auto`
- `PRINTPIPE_OPENAI_IMAGE_OUTPUT_FORMAT` default `png`
- `PRINTPIPE_OPENAI_IMAGE_BASE_URL` default `https://api.openai.com/v1`

## Evidence

- Input-processing tests cover missing provider configuration.
- Input-processing tests cover OpenAI selected without `OPENAI_API_KEY`.
- Input-processing tests cover a local fake OpenAI-compatible HTTP server returning `b64_json`.
- CLI tests cover `--prompt-image-provider openai` failure when no key is configured.
- Web tests cover provider selector rendering and launch metadata.

## Still Missing

- Live OpenAI/API-key evidence.
- Cost/quality policy for hosted prompt-image providers.
- Physical print validation.
