# Wave 6 Integration Summary

Status: complete as a software foundation; not physically print-validated.

## What Landed

Wave 6 added the first material-rule layer for PrintPipe:

- Shared registry and scoped settings-delta helpers in `src/printpipe/materials/core.py`.
- PLA and PLA+ foundation intent in `src/printpipe/materials/pla.py`.
- PETG foundation overrides in `src/printpipe/materials/petg.py`.
- TPU 90A, TPU 95A, and SUNLU TPU 90A slipper-derived rules in `src/printpipe/materials/tpu.py`.
- ABS and ASA conservative high-temperature material rules in `src/printpipe/materials/abs_asa.py`.
- PC, PA, and PA-CF conservative engineering-material rules in `src/printpipe/materials/pc_pa.py`.
- Unit tests for every material family and the shared reason/delta registry.

`printpipe.materials` intentionally exports only the shared core API. Concrete
families are imported from their own modules so `MaterialRule`, `PreflightNote`,
and family-specific helper names do not collide at package import time.

## What This Means For The 142-Item Roadmap

- Material families for PLA, PETG, TPU, ABS/ASA, PC, and PA now exist.
- Filament override rules now exist for those families.
- Process override rules now exist for those families.
- Every emitted software override in the Wave 6 rule modules has a human-readable reason.

## What Is Still Not Done

- These are foundations, not final brand-specific profiles for every spool.
- Bambu/Orca defaults are not fully loaded for every material and printer pair.
- The run pipeline does not yet let the user select a material and emit the final material-specific `.3mf`.
- Physical test objects for TPU, PLA, and PETG have not been printed.
- Some settings still need live Bambu enum/profile validation at bundle time.

## Verification

Targeted Wave 6 tests:

```text
31 passed
```

Full-suite verification should be run after integration with:

```bash
.venv/bin/python -m pytest
```
