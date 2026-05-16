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

Status: complete. Outputs are covered by module tests in `tests/test_mesh_repair.py`, `tests/test_bambu_profile_sources.py`, `tests/test_bambu_threemf_mesh_adapter.py`, `tests/test_bambu_slicer_slipper_fixture.py`, `tests/test_pipeline_existing_mesh.py`, and `tests/test_slipper_manifest.py`.

1. Done: optional real mesh repair API skeleton, with live tests skipped when `trimesh` is absent.
2. Done: Bambu profile source discovery and copy helpers.
3. Done: ASCII STL to Bambu-native 3MF adapter utilities.
4. Done: compact slipper v3 slice estimate fixture and parser coverage.
5. Done: existing-mesh pipeline orchestrator skeleton.
6. Done: slipper POC manifest and migration comparison doc without copying large artifacts.

## Wave 5 - Generic Object Expansion

Status: complete. Outputs are covered by `tests/test_object_fixture_*.py`, `tests/test_existing_stl_pipeline_bundle.py`, and `tests/test_wave5_orientation_review_doc.py`.

1. Done: figurine test object.
2. Done: cup/vase test object.
3. Done: flat bracket/wrench test object.
4. Done: decorative organic object.
5. Done: existing STL import-to-bundle fixture test.
6. Done: cross-object orientation review.

## Wave 6 - Filament Coverage

Status: complete as a software foundation. Outputs are covered by `tests/test_materials_core.py`, `tests/test_materials_pla.py`, `tests/test_materials_petg.py`, `tests/test_materials_tpu.py`, `tests/test_materials_abs_asa.py`, and `tests/test_materials_pc_pa.py`.

1. Done: PLA and PLA+ foundation rules.
2. Done: PETG foundation rules.
3. Done: TPU 90A, TPU 95A, and SUNLU TPU 90A slipper-derived rules.
4. Done: ABS/ASA foundation rules.
5. Done: PC/PA/PA-CF foundation rules.
6. Done: shared settings reason catalog and material delta helpers.

## Wave 7 - Local UX

Status: complete as a local UX foundation. Outputs are covered by `tests/test_reports_html.py`, `tests/test_cli_serve.py`, `tests/test_web_server.py`, `tests/test_web_options.py`, `tests/test_web_status.py`, and `tests/test_web_artifacts.py`.

1. Done: local HTML report polish.
2. Done: stdlib local web UI shell.
3. Done as UI foundation: file input/drop-zone surface.
4. Done as UI foundation: printer and filament selectors.
5. Done as snapshot model: progress states from manifest/report files.
6. Done as foundation: safe report/artifact links and download route.

## Wave 8 - Packaging

Status: complete as a packaging/environment foundation. Outputs are covered by `tests/test_env_macos.py`, `tests/test_env_windows.py`, `tests/test_env_bambu_studio.py`, `tests/test_env_bambu_profiles.py`, `tests/test_env_dependencies.py`, `tests/test_env_doctor.py`, and `tests/test_cli_doctor.py`.

1. Done: macOS dependency/runtime detection.
2. Done: Windows dependency/runtime detection.
3. Done: Bambu Studio install path detection.
4. Done: Bambu user profile detection.
5. Done as docs/foundation: installer/package notes.
6. Done: troubleshooting guide and `printpipe doctor`.

## Wave 9 - Beta and Regression

Status: complete as beta/regression infrastructure. Outputs are covered by `tests/test_beta_slipper_dogfood_doc.py`, `tests/test_beta_non_slipper_runs_doc.py`, `tests/test_beta_failures.py`, `tests/test_beta_regression.py`, `tests/test_github_issue_templates.py`, and `tests/test_beta_onboarding_docs.py`.

1. Done as gated plan: slipper full validation.
2. Done as beta plan: three-plus non-slipper beta runs.
3. Done: failure log template and structured failure capture helpers.
4. Done as foundation: regression manifest helpers.
5. Done: GitHub issue templates.
6. Done: beta onboarding docs.

## Wave 10 - Hosted Future Planning

Status: complete as hosted-future planning. Outputs are covered by `tests/test_cloud_backend_api_doc.py`, `tests/test_cloud_queue_workers_doc.py`, `tests/test_cloud_storage_auth_doc.py`, `tests/test_cloud_cost_billing_doc.py`, `tests/test_cloud_meshgen_decision_doc.py`, and `tests/test_cloud_local_power_user_doc.py`.

1. Done: backend API sketch.
2. Done: queue/worker sketch.
3. Done: storage/auth sketch.
4. Done: cost model.
5. Done: cloud meshgen worker decision and gates.
6. Done: keep-local-power-user plan.
