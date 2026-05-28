# Wave 67 - Prompt Provider Workbench Receipts

## Goal

Make prompt-only provider failures visible where Zohar actually makes print decisions: the run-detail workbench.

## What Changed

- Added `prompt_reference` to the run-detail contract when a `prompt_reference_generation` receipt exists.
- Added a workbench panel for prompt-provider receipt details.
- The panel shows provider, privacy mode, estimated cost, max cost, estimated latency, budget status, and remote-upload/storage note.
- The input/reference pipeline step now summarizes all matching receipts instead of taking the first successful receipt.
- Prompt-reference failures now block the print verdict.

## Why

Prompt-only runs can start with a successful `classify_input` receipt and then fail at `prompt_reference_generation`. The old workbench could make that look like the input/reference step succeeded, which is misleading. The UI should not be calmer than the receipts.

## Evidence

- Contract regression covers OpenAI cost-cap failure and provider quote extraction.
- Web regression covers the prompt-provider receipt panel and failed input/reference pipeline row.
- Focused affected suite passed after implementation.

## Still Missing

- Real OpenAI/API-key smoke run evidence.
- Side-by-side provider quality comparison.
- Physical print validation.
