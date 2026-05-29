# PrintPipe Architecture

## Principle

Mesh generation is not the product. The product is the verified bridge from messy reference to printable Bambu project.

## V1 Shape

```text
Local CLI / local app
  -> run folder manager
  -> input processor
  -> meshgen provider interface
  -> mesh repair + validation
  -> orientation + bed-fit engine
  -> Bambu profile/settings engine
  -> Bambu-native 3MF bundler
  -> Bambu CLI slice gate
  -> receipt/report generator
```

## Module Boundaries

- `runs`: creates immutable run folders and artifact paths.
- `inputs`: accepts prompt, image, GIF, video, and existing mesh references.
- `meshgen`: provider interface for hosted or local model calls.
- `mesh`: repair, topology validation, and export.
- `geometry`: orientation, scale, bed fit, and support-risk scoring.
- `calibration`: physical validation artifacts such as flexible-material coupons.
- `bambu`: printer profiles, filament profiles, process profiles, enum validation, 3MF bundling, and slice parsing.
- `reports`: HTML/Markdown/JSON receipts.
- `cli`: user-facing command line.

## Input Truth Table

| Input | Pipeline status | Receipt behavior |
| --- | --- | --- |
| Existing mesh | Production spine for v1 foundation. | Imports existing geometry, repairs it, writes oriented STL, preview artifacts, Bambu `.3mf`, validation report, and optional slice receipt. |
| Image/GIF/video | Wired through a configured media meshgen command adapter. | Writes extracted/selected references and contact sheet artifacts, then either generates a mesh and continues through repair/orient/bundle/report, or fails `meshgen` with a provider-configuration receipt when neither `PRINTPIPE_MEDIA_MESHGEN_COMMAND` nor `PRINTPIPE_HUNYUAN3D_COMMAND` is set. |
| Prompt + image | CLI and local web wired. | `printpipe run image.png --prompt "..."` and the local web file-plus-prompt form prepare the reference image normally and pass the prompt through as `MeshGenRequest.prompt_hint`. |
| Prompt only | CLI and local web wired through selectable reference-image providers. | `printpipe run --prompt "..."` and prompt-only web runs write `00_input/prompt.txt`, then use `auto`, `command`, or `openai` prompt-image provider selection to create a reference image before continuing through the same media-meshgen/repair/orient/bundle spine. If no provider is configured, the run fails at `prompt_reference_generation` with receipts; the run-detail workbench and static run reports surface provider quote/budget/privacy receipts when present. |

## Hard Gates

1. Mesh topology must be validated after generation and after repair.
2. Bed fit must be validated before bundling.
3. Bambu profile enum values must be schema/source checked before bundling.
4. 3MF must be Bambu-native enough to open without rejection.
5. Bambu CLI slice must pass before the app calls a run successful.

## Current Command Target

The current end-to-end command target uses an existing mesh:

```bash
printpipe run input.stl --slice
```

Image/GIF/video now uses the same repair/orient/bundle path after a configured media meshgen command writes a mesh. Use the ComfyUI preset for an exported API workflow ending in `SaveGLB`, the generic hook for any adapter that accepts PrintPipe's command arguments, or the Hunyuan-specific hook for that local adapter:

```bash
printpipe media-meshgen-template --preset comfyui-api --output scripts/media_meshgen_adapter.py
printpipe media-meshgen-comfyui-inspect workflows/image_to_glb.json
printpipe media-meshgen-configure \
  --command "python scripts/media_meshgen_adapter.py" \
  --params-json '{"comfyui_workflow":"workflows/image_to_glb.json","comfyui_image_paths":["12.inputs.image"]}'
printpipe media-meshgen-smoke reference.png --command "printpipe media-meshgen-heightfield"
export PRINTPIPE_HUNYUAN3D_COMMAND="/path/to/hunyuan_adapter"
export PRINTPIPE_PROMPT_IMAGE_COMMAND="/path/to/image_adapter --prompt-file {prompt_file} --output {output}"
export OPENAI_API_KEY="sk-..."  # optional when --prompt-image-provider openai is selected
export PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD="0.012"
export PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD="0.05"
printpipe run input.gif \
  --printer "Bambu Lab P2S" \
  --material "SUNLU TPU 90A" \
  --use-case "wearable slipper"

printpipe run --prompt "small ergonomic desk hook" --prompt-image-provider openai
```

OpenAI prompt-image cost is treated as a user-configured estimate, not a hardcoded
pricing promise. If `PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD` is set and the estimate
is missing or above the cap, the prompt-reference stage fails before making the
remote API request.

The first real milestone is not a polished UI. It is a reproducible run folder with a slice-verified `.3mf` and receipts.

Flexible-material runs also add `40_geometry/flex_coupon_40x15x3.stl` as a calibration artifact so the user can print a small TPU validation coupon before a long final part.
