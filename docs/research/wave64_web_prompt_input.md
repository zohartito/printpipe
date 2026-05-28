# Wave 64 - Local Web Prompt Input

## Goal

Bring the local web new-run flow up to parity with the Wave 63 CLI prompt paths.

## What Changed

- Added a `Prompt` field to the local web new-run form.
- Allowed `/runs` multipart posts with a prompt and no uploaded file.
- Prompt-only web runs now create `00_input/prompt.txt` and a prompt manifest.
- Prompt-only web runs reuse the same `PRINTPIPE_PROMPT_IMAGE_COMMAND` path as `printpipe run --prompt`.
- File-plus-prompt web runs preserve the prompt in launch options and pass it into the pipeline as `prompt_hint`.
- Launch options now record `input_mode` as `file`, `prompt`, or `file+prompt`.

## Evidence

- Added tests for home form prompt rendering.
- Added tests for prompt-only web run creation and honest failed receipts when no prompt-image command is configured.
- Added tests for file-plus-prompt launch metadata preservation.

## Still Missing

- Real prompt-image provider adapter.
- Web UI for choosing local/hosted image generation provider.
- Physical print validation for the generated objects.
