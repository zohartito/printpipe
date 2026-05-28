# Wave 66 - Prompt Image Quote and Budget Receipts

## Goal

Make prompt-image provider use auditable before remote work starts.

## What Changed

- Added provider quote metadata to prompt-reference receipts.
- Command provider records local/user-configured zero-cost quote metadata.
- OpenAI provider records remote API privacy mode, estimated latency, estimated cost, and max-cost metadata.
- Added fail-closed cost cap behavior through `PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD`.
- OpenAI estimated cost is supplied by `PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD` instead of being hardcoded.

## Why

Provider pricing can drift. PrintPipe should not pretend a baked-in dollar value is current truth. The app now records the estimate it was given and blocks remote work when the user sets a cap that cannot be checked.

## New Environment Variables

- `PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD`
- `PRINTPIPE_OPENAI_IMAGE_ESTIMATED_SECONDS`
- `PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD`

## Evidence

- Input-processing tests cover OpenAI quote metadata.
- Input-processing tests cover command provider zero-cost quote metadata.
- Input-processing tests cover fail-closed behavior when max cost is set but no estimate exists.
- Input-processing tests cover blocking when the estimate exceeds the cap.
- CLI tests cover cost-cap failure surfacing in reports.

## Still Missing

- Live OpenAI/API-key smoke evidence.
- Provider quality comparison across real generated references.
- Physical print validation.
