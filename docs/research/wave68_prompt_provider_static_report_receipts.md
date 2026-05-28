# Wave 68 - Prompt Provider Static Report Receipts

## Goal

Keep prompt-provider evidence portable in the run folder, even when the local web workbench is not open.

## What Changed

- Markdown reports now add a `Prompt Reference` section when a `prompt_reference_generation` receipt exists.
- HTML reports now add a `Prompt Reference` section with provider, stage status, privacy mode, estimated cost, max cost, latency, budget status, and remote prompt-storage note.
- OpenAI cost-cap failures are promoted into readable report sections instead of only appearing inside raw stage metrics.

## Why

The workbench is useful during active debugging, but the run folder itself is the durable program artifact. If a prompt-only run is blocked before remote work because of a budget cap, that reason should be obvious in `run_report.md` and `run_report.html`.

## Evidence

- Markdown report regression covers OpenAI quote and budget fields.
- HTML report regression covers the prompt-reference section and escaped rendered values.

## Still Missing

- Real live OpenAI/API-key smoke evidence.
- Provider quality comparison with generated references.
- Physical print validation.
