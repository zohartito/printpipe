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
- `inputs`: accepts image, GIF, video, and existing mesh references.
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
| Image/GIF/video | Wired through the configured local Hunyuan3D adapter. | Writes extracted/selected references and contact sheet artifacts, then either generates a mesh and continues through repair/orient/bundle/report, or fails `meshgen` with a provider-configuration receipt when `PRINTPIPE_HUNYUAN3D_COMMAND` is unset. |
| Prompt + image | Provider contract only. | `MeshGenRequest.prompt_hint` can reach configured providers, but CLI/web do not persist or route prompt hints yet. |
| Prompt only | Unsupported. | No run mode exists because the pipeline still needs concrete source geometry or visual references. |

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

Image/GIF/video now uses the same repair/orient/bundle path after the configured Hunyuan3D command writes a mesh:

```bash
export PRINTPIPE_HUNYUAN3D_COMMAND="/path/to/hunyuan_adapter"
printpipe run input.gif \
  --printer "Bambu Lab P2S" \
  --material "SUNLU TPU 90A" \
  --use-case "wearable slipper"
```

The first real milestone is not a polished UI. It is a reproducible run folder with a slice-verified `.3mf` and receipts.

Flexible-material runs also add `40_geometry/flex_coupon_40x15x3.stl` as a calibration artifact so the user can print a small TPU validation coupon before a long final part.
