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
- `bambu`: printer profiles, filament profiles, process profiles, enum validation, 3MF bundling, and slice parsing.
- `reports`: HTML/Markdown/JSON receipts.
- `cli`: user-facing command line.

## Hard Gates

1. Mesh topology must be validated after generation and after repair.
2. Bed fit must be validated before bundling.
3. Bambu profile enum values must be schema/source checked before bundling.
4. 3MF must be Bambu-native enough to open without rejection.
5. Bambu CLI slice must pass before the app calls a run successful.

## First Command Target

```bash
printpipe run input.gif \
  --printer "Bambu Lab P2S 0.4 nozzle" \
  --filament "SUNLU TPU 90A" \
  --target-size 295mm
```

The first real milestone is not a polished UI. It is a reproducible run folder with a slice-verified `.3mf` and receipts.

