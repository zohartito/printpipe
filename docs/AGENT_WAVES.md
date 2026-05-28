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

## Wave 11 - Local Pipeline Integration

Status: complete as a local pipeline spine. Outputs are covered by the full test suite and by the run-folder contract used by CLI and web smoke checks.

1. Done: image/GIF/video input preparation records extracted, cleaned, selected, and contact-sheet artifacts.
2. Done: local Hunyuan3D command provider contract exists without forcing hosted credentials.
3. Done: geometry helpers cover axes, bed fit, cavity/opening notes, and support-burden scoring.
4. Done: Bambu/Orca profile default discovery is available through environment diagnostics.
5. Done: slice receipts/log artifacts are stable even before live slicing is enabled.
6. Done: web `POST /runs` creates run folders and reports for media inputs.

## Wave 12 - Artifact and Repair Integration

Status: complete as artifact/repair infrastructure. Outputs are covered by `tests/test_mesh_repair.py`, `tests/test_web_artifacts.py`, `tests/test_reports_html.py`, and the existing-STL pipeline tests.

1. Done: ASCII STL orientation artifact writer stores oriented mesh and sidecar JSON.
2. Done: optional `trimesh` repair extra writes repair stats and repaired mesh artifacts.
3. Done: contact-sheet and bed-fit previews are discoverable as local report artifacts.
4. Done: Bambu CLI path discovery and safe command construction are covered by tests.
5. Done: web artifact grouping includes reports, mesh artifacts, bundles, slice logs, and previews.
6. Done: packaging and beta blockers are documented honestly instead of marked physically complete.

## Wave 13 - Existing STL End-to-End Spine

Status: complete for existing mesh inputs. Outputs are covered by `tests/test_pipeline_existing_mesh.py`, `tests/test_existing_stl_pipeline_bundle.py`, `tests/test_cli_run.py`, `tests/test_web_server.py`, `tests/test_bambu_slicer.py`, `tests/test_reports_html.py`, and `tests/test_preflight.py`.

1. Done: `printpipe run input.stl` now runs import -> repair -> orient -> bed fit -> Bambu 3MF bundle -> validation -> report.
2. Done: web STL uploads use the same existing-mesh pipeline and expose the resulting `.3mf`.
3. Done: failed mesh repair stops before orientation/bundling and writes a failed report.
4. Done: requested Bambu CLI slice failures become slice receipts instead of raw exceptions.
5. Done: HTML reports embed previews, highlight bundles, and render pre-print checklist items.
6. Done: roadmap items 100, 102, and 119 moved from partial to done; live Bambu slicing and physical beta remain partial until artifact-backed evidence exists.

## Wave 14 - Live Slice Gate Hardening

Status: F3 complete as a PrintPipe feature; successful live slicing remains blocked by a local Bambu Studio CLI segfault. Outputs are covered by `tests/test_bambu_slicer.py`, `tests/test_pipeline_existing_mesh.py`, and `tests/test_cli_run.py`.

1. Done: `printpipe run --slice` preserves run/report paths on requested slice failure instead of hiding the receipt behind an argparse error.
2. Done: `--bambu-cli` now requires `--slice`, and `--slice` is rejected for image/GIF/video inputs until meshgen is wired into the orchestrator.
3. Done: missing Bambu CLI is a failed requested slice gate; not-requested slicing remains a skipped gate.
4. Done: slice receipts now include `slice_requested=true`, command, executable, checked candidates, logs, return code, warnings, errors, and G-code-derived estimates when available.
5. Done: negative subprocess return codes are classified as signals, including `SIGSEGV` for Bambu Studio crashes.
6. Found: Bambu Studio 02.06.00.51 on macOS 26.5 crashes with signal 11 for CLI `--slice` on both a PrintPipe `.3mf` and a direct tiny STL; follow-up F13 owns isolating that Bambu CLI/runtime issue.

## Wave 15 - Run Detail Contract and Edit Recipes

Status: complete. Outputs are covered by `tests/test_run_detail_contract.py`, `tests/test_edit_recipes.py`, and `tests/test_web_server.py`.

1. Done: added a typed run-detail contract that reads manifest/report/artifact state into a workbench-friendly payload.
2. Done: added non-destructive edit recipe objects for scale, target dimensions, geometry intent, support strategy, and freeform instruction.
3. Done: edit runs are created as sibling run folders with `parent_run` metadata and `edit_recipe.json`.
4. Done: validation keeps edit recipe values positive, bounded, and explicit.
5. Done: run detail data now includes verdict, validation, pipeline, artifact, warning, and rebuild context.
6. Done: existing web route data contract remains backward-compatible for recent runs and reports.

## Wave 16 - Workbench UI Integration

Status: complete. Outputs are covered by `tests/test_web_server.py` and browser verification against a local run route.

1. Done: `/runs/<id>` renders the top-level "Can this run print?" verdict strip.
2. Done: model workbench layout now uses preview tabs, a large model/bed area, risk markers, and bottom metrics.
3. Done: edit sidebar includes input/mesh summary, slipper fit context, scale/target/opening/arch controls, support strategy, and rebuild action.
4. Done: artifact links are kept near the edit/rebuild workflow.
5. Done: CSS keeps the workbench responsive without copying prototype-only decorative code.
6. Done: Cursor prototype hierarchy was incorporated into the live stdlib web route.

## Wave 17 - Non-Destructive Edit Route

Status: complete. Outputs are covered by `tests/test_web_server.py`, `tests/test_edit_recipes.py`, and `tests/test_run_detail_contract.py`.

1. Done: web `POST /runs/<id>/edits` parses form fields into an `EditRecipe`.
2. Done: edit submissions preserve the parent run and redirect to the child workbench.
3. Done: parent inputs are copied into the child run without mutating parent artifacts.
4. Done: rebuild metadata is visible in the run-detail contract.
5. Done: edit controls are wired to stable field names for future semantic geometry work.
6. Done: invalid edit submissions fail before creating misleading output.

## Wave 18 - Rebuild From Edit Recipes

Status: complete. Outputs are covered by `tests/test_pipeline_existing_mesh.py`, `tests/test_cli_run.py`, `tests/test_geometry_artifacts.py`, and `tests/test_web_server.py`.

1. Done: `load_run()` reconstructs `RunLayout` from an existing run manifest.
2. Done: existing-mesh pipeline can operate inside a pre-created run layout.
3. Done: `run_edit_recipe_pipeline()` resolves edit source meshes from child input or parent artifacts.
4. Done: deterministic edit rebuild applies scale fields to ASCII STL geometry and records a sidecar report.
5. Done: unsupported semantic fields such as targets, support strategy, freeform instruction, and opening/arch/wall intent are preserved as warnings instead of fake geometry claims.
6. Done: `printpipe rebuild-edit` rebuilds saved edit runs from the CLI.

## Wave 19 - Deterministic Run Preview

Status: complete. Outputs are covered by `tests/test_geometry.py`, `tests/test_pipeline_existing_mesh.py`, `tests/test_web_artifacts.py`, and browser verification.

1. Done: added bounds-only `run_detail_model_preview.svg` and JSON sidecar artifacts.
2. Done: existing-mesh and edit-rebuild pipelines emit the model preview into `40_geometry/`.
3. Done: web artifact discovery prioritizes the model preview ahead of bed-fit/contact-sheet previews.
4. Done: run detail embeds the SVG preview image when available, with the placeholder kept only as fallback.
5. Done: preview JSON explicitly records `semantic_claim=false`.
6. Done: browser verification showed the generated 960x600 SVG loading in the live workbench.

## Wave 20 - Input Truth Receipts

Status: complete. Outputs are covered by `tests/test_cli_run.py`, `tests/test_web_server.py`, and `tests/test_pipeline_existing_mesh.py`.

1. Done: CLI media runs now write reports with a failed `meshgen` receipt and return nonzero instead of looking complete.
2. Done: web media uploads still create a run and redirect to the report/workbench, but the report carries `meshgen=failed`.
3. Done: README and architecture docs include a current input support table.
4. Done: existing mesh remains the only end-to-end printable spine.
5. Done: prompt-plus-image is documented as provider-contract-only.
6. Done: prompt-only is documented as unsupported.

## Wave 21 - Slice Crash Message Surfacing

Status: complete. Outputs are covered by `tests/test_bambu_slicer.py`, `tests/test_pipeline_existing_mesh.py`, and `tests/test_cli_run.py`.

1. Done: failed slice receipts promote the first classified slicer error into the stage message.
2. Done: signal crashes now surface as messages such as `Bambu CLI slice failed: slicer terminated by signal 11 (SIGSEGV).`
3. Done: pipeline warnings and CLI errors inherit the concrete slice failure reason.
4. Done: run-detail readiness reads real slice `return_code` and `errors`, not only synthetic `slice_success` metrics.
5. Done: raw slice JSON metrics still preserve the full warning/error tuple.
6. Remaining: F13 still owns isolating or bypassing the Bambu Studio 2.6.00.51/macOS 26.5 CLI crash itself.

## Wave 22 - Documentation and GitHub Sync

Status: complete for this pass once the orchestrator commit is pushed. Outputs are covered by the full test suite and this ledger.

1. Done: updated roadmap/backlog to reflect Waves 15 through 21.
2. Done: kept Cursor prototypes and UI reference review as design artifacts rather than rewriting them into app code blindly.
3. Done: verified full test suite after each high-risk integration wave.
4. Done: left Bambu CLI segfault as an explicit open frontier, not a hidden failure.
5. Done: prepared all current work for a single GitHub commit.
6. Next: continue with F4/F13 or physical/beta validation after this push.

## Wave 23 - Configured Media Meshgen Spine

Status: complete for the software path. Outputs are covered by `tests/test_pipeline_existing_mesh.py`, `tests/test_cli_run.py`, and `tests/test_web_server.py`.

1. Done: image/GIF/video inputs no longer hard-stop before meshgen.
2. Done: media runs use selected reference artifacts as Hunyuan3D `source_paths` and `reference_images`.
3. Done: configured Hunyuan3D output continues through repair, orientation, preview generation, Bambu `.3mf` bundle, validation, reports, and optional slice gate.
4. Done: missing `PRINTPIPE_HUNYUAN3D_COMMAND` now produces a failed `meshgen` receipt with provider id `hunyuan3d`.
5. Done: CLI coverage proves a fake configured Hunyuan command can turn a PNG input into `generated_mesh_hunyuan3d.3mf`.
6. Remaining: real local Hunyuan runtime configuration and F13 Bambu CLI SIGSEGV isolation are still outside this wave.

## Wave 24 - TPU Flex Coupon Artifact

Status: complete for software artifact generation. Outputs are covered by `tests/test_flex_coupon.py`, `tests/test_web_artifacts.py`, and `tests/test_pipeline_existing_mesh.py`.

1. Done: added a deterministic ASCII STL flex-coupon generator for flexible-material validation.
2. Done: TPU/flexible pipeline reports now include `validation.flex_coupon` and `40_geometry/flex_coupon_40x15x3.stl`.
3. Done: the `flex_coupon_first` checklist item records the coupon artifact path in metadata.
4. Done: web artifact discovery recognizes `calibration_mesh` artifacts so the coupon can be opened/downloaded from the run workbench.
5. Remaining: physical F9 validation still needs real PLA/PETG/TPU coupon or small-object prints with photos and notes.

## Wave 25 - Local Open-Folder Affordance

Status: complete for local CLI/web affordances. Outputs are covered by `tests/test_cli_run.py` and `tests/test_web_server.py`.

1. Done: added `printpipe open-folder <run> --target run|report|bundle`.
2. Done: added `--dry-run` so tests and scripts can resolve the target folder without launching Finder/Explorer.
3. Done: run-detail artifacts now include local POST buttons for opening bundle and report folders.
4. Done: web folder opening uses a safe run-root lookup and injectable opener for tests.
5. Remaining: direct "send to printer" remains separate from this local folder-opening affordance.

## Wave 26 - Filesystem Readability Receipts

Status: complete for F2 and F12. Outputs are covered by `tests/test_env_doctor.py`, `tests/test_web_status.py`, and `tests/test_cli_doctor.py`.

1. Done: `printpipe doctor` now includes a filesystem section for workspace paths and configured artifact paths.
2. Done: `PRINTPIPE_ARTIFACT_PATHS` can be used to have doctor check external artifact locations without changing the run pipeline.
3. Done: unreadable or missing filesystem paths report warning status, path, existence, readability, and a concrete recovery action.
4. Done: web run status now resolves artifact access into `present`, `inside_run_root`, `readable`, and `state`.
5. Done: unreadable external artifacts are counted as unusable and reported instead of crashing status generation.
6. Remaining: F1 still owns any broader macOS Desktop/TCC recovery guidance for the primary checkout.
