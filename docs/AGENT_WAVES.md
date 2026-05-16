# Agent Waves

This is how the 142 roadmap items get executed without creating 142 chaotic agents.

Rule: at most 6 active agents per wave. Each agent owns a coherent work package with disjoint files or a read-only research scope. The orchestrator integrates, tests, commits, and updates the roadmap between waves.

## Wave 1 - Foundation Research and Extraction

Status: complete. Outputs are in `docs/research/wave1_*.md`.

1. Done: requirements/spec agent turned the brainstorm into v1 acceptance criteria.
2. Done: repo architecture agent reviewed package structure and suggested boundaries.
3. Done: slipper extraction agent audited `/Users/zohartito/Desktop/slipper_3d` for reusable code.
4. Done: Bambu schema agent mapped profile files, enum sources, and 3MF requirements.
5. Done: meshgen provider agent compared local/API/HF/Replicate options.
6. Done: validation strategy agent defined tests, fixtures, and gates.

## Wave 2 - Core Pipeline Skeleton

Status: complete. Outputs are covered by module tests in `tests/test_inputs.py`, `tests/test_meshgen.py`, `tests/test_mesh_validate.py`, `tests/test_bambu_profiles.py`, `tests/test_bambu_threemf.py`, and `tests/test_reports.py`.

1. Done before dispatch: run folder system and shared contracts.
2. Done: input processing skeleton.
3. Done: meshgen provider interface and existing-mesh provider.
4. Done: mesh topology validation skeleton.
5. Done: Bambu settings/profile engine skeleton.
6. Done: Bambu-native 3MF bundler skeleton.
7. Done: receipt/report skeleton.

## Wave 3 - Verification Spine

Status: complete. Outputs are covered by module tests in `tests/test_bambu_slicer.py`, `tests/test_bambu_profile_report.py`, `tests/test_geometry.py`, `tests/test_reports_html.py`, `tests/test_cli_run.py`, and `tests/test_fixtures.py`.

1. Done: Bambu CLI slice gate skeleton and warning classifier.
2. Done: Settings delta JSON/Markdown report utilities.
3. Done: Orientation and bed-fit scoring skeleton.
4. Done: HTML run report.
5. Done: CLI command wrapper for `run`, `status`, and `open-report`.
6. Done: Regression fixture suite foundation.

## Wave 4 - Slipper POC Migration

1. Import slipper input fixtures.
2. Port current mesh repair stats.
3. Port current Bambu profiles.
4. Port current 3MF generation.
5. Port current slice estimate parser.
6. Compare output against known slipper artifacts.

## Wave 5 - Generic Object Expansion

1. Figurine test object.
2. Cup/vase test object.
3. Flat bracket/wrench test object.
4. Decorative organic object.
5. Existing STL import test.
6. Cross-object orientation review.

## Wave 6 - Filament Coverage

1. PLA rules.
2. PETG rules.
3. TPU rules.
4. ABS/ASA rules.
5. PC/PA rules.
6. Settings reason catalog.

## Wave 7 - Local UX

1. Local HTML report polish.
2. Local web UI shell.
3. Drag/drop input.
4. Printer/filament selectors.
5. Progress states.
6. Open/download artifacts.

## Wave 8 - Packaging

1. macOS dependency detection.
2. Windows dependency detection.
3. Bambu Studio path detection.
4. Bambu user profile detection.
5. Installer/package notes.
6. Troubleshooting guide.

## Wave 9 - Beta and Regression

1. Slipper full validation.
2. Three non-slipper beta runs.
3. Failure log template.
4. Regression test harness.
5. GitHub issue templates.
6. Beta onboarding docs.

## Wave 10 - Hosted Future Planning

1. Backend API sketch.
2. Queue/worker sketch.
3. Storage/auth sketch.
4. Cost model.
5. Cloud meshgen worker plan.
6. Keep-local-power-user plan.
