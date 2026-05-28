# Wave 63 - Prompt-Only CLI Input

## Question

Can PrintPipe accept a prompt without an input image while staying honest about
the need for a visual reference before mesh generation?

## Implementation

Added a prompt-only CLI path:

```bash
printpipe run --prompt "small ergonomic desk hook"
```

The run writes:

```text
00_input/prompt.txt
```

Prompt-only then uses a configured image generator command:

```bash
export PRINTPIPE_PROMPT_IMAGE_COMMAND='your-image-tool --prompt-file {prompt_file} --output {output}'
```

The generated reference image is stored under:

```text
10_frames/prompt_reference/prompt_reference.png
```

After that, the existing reference cleanup, selection, contact sheet, Hunyuan3D
meshgen, repair, orientation, bundle, and report path is reused.

## Prompt Plus Reference

The CLI also accepts:

```bash
printpipe run image.png --prompt "small ergonomic desk hook"
```

That keeps the image path as the concrete reference and passes the prompt to
meshgen providers as `prompt_hint`.

## Failure Boundary

If `PRINTPIPE_PROMPT_IMAGE_COMMAND` is unset, prompt-only runs fail at
`prompt_reference_generation` and still write the normal run report artifacts.
This avoids claiming prompt-only geometry exists before an image provider is
configured.

## Tests

Added CLI coverage for:

- prompt-only missing generator command -> failed receipts
- prompt-only configured image command + configured Hunyuan command -> Bambu
  `.3mf` bundle

## Remaining

The local web UI still needs a prompt field. A real prompt-image adapter still
needs to be selected/configured; the current contract is command-based so local,
hosted, or API image providers can be swapped in later.
