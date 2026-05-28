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
6. Found: Bambu Studio 02.06.00.51 on macOS 26.5 crashed with signal 11 for CLI `--slice` on sparse/direct inputs; Wave 36 later isolated the supported full-settings `.3mf` path.

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
6. Superseded: Wave 36 isolated the supported non-crashing full-settings `.3mf` path.

## Wave 22 - Documentation and GitHub Sync

Status: complete for this pass once the orchestrator commit is pushed. Outputs are covered by the full test suite and this ledger.

1. Done: updated roadmap/backlog to reflect Waves 15 through 21.
2. Done: kept Cursor prototypes and UI reference review as design artifacts rather than rewriting them into app code blindly.
3. Done: verified full test suite after each high-risk integration wave.
4. Done: left Bambu CLI segfault as an explicit open frontier, not a hidden failure.
5. Done: prepared all current work for a single GitHub commit.
6. Superseded: F4 and F13 are now complete; physical/beta validation remains.

## Wave 23 - Configured Media Meshgen Spine

Status: complete for the software path. Outputs are covered by `tests/test_pipeline_existing_mesh.py`, `tests/test_cli_run.py`, and `tests/test_web_server.py`.

1. Done: image/GIF/video inputs no longer hard-stop before meshgen.
2. Done: media runs use selected reference artifacts as Hunyuan3D `source_paths` and `reference_images`.
3. Done: configured Hunyuan3D output continues through repair, orientation, preview generation, Bambu `.3mf` bundle, validation, reports, and optional slice gate.
4. Done: missing `PRINTPIPE_HUNYUAN3D_COMMAND` now produces a failed `meshgen` receipt with provider id `hunyuan3d`.
5. Done: CLI coverage proves a fake configured Hunyuan command can turn a PNG input into `generated_mesh_hunyuan3d.3mf`.
6. Remaining: real local Hunyuan runtime configuration is still outside this wave; Wave 36 completed F13.

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

## Wave 27 - macOS TCC Recovery Guidance

Status: complete for F1. Outputs are covered by `tests/test_troubleshooting_docs.py`.

1. Done: added a troubleshooting section for macOS Desktop, Documents, Downloads, external-drive, and cloud-folder privacy/TCC blocks.
2. Done: documented why `chmod` is usually the wrong first fix for TCC-denied paths.
3. Done: documented the preferred recovery path: move to `~/Projects` or grant Full Disk Access to Terminal/iTerm/Codex/Cursor/VS Code/the packaged app.
4. Done: documented the required quit/reopen step after changing macOS privacy grants.
5. Done: documented `PRINTPIPE_ARTIFACT_PATHS=... printpipe doctor` for checking external artifact readability.
6. Remaining: real packaged-app permission prompts belong with F10 macOS packaging smoke work.

## Wave 28 - Slipper PrintPipe Dogfood

Status: complete for F8 and original item 103 as software dogfood. Outputs are covered by `tests/test_cli_run.py`, `tests/test_beta_slipper_dogfood_doc.py`, and `tests/test_slipper_manifest.py`.

1. Done: added CLI `--material`, `--printer`, and `--use-case` flags so dogfood reports do not default high-risk TPU slippers to Generic PLA.
2. Done: wired SUNLU TPU 90A material intent into the Bambu `.3mf` project settings, including slipper filament/process profile IDs and key TPU support/brim/shell/temperature overrides.
3. Done: ran `/Users/zohartito/Desktop/slipper_3d/output/slipper_size11_v2c_wide_upper_textured.stl` through PrintPipe as `runs/20260528-042826-slipper-size11-v2c-wide-upper-textured`.
4. Done: verified the run repaired the mesh to watertight output, fit the 256 x 256 mm P2S bed with 21.92 mm minimum XY margin, validated the `.3mf`, and recorded 0 warnings.
5. Done: verified the TPU flex coupon artifact and checklist requirement are present in the dogfood run.
6. Superseded: Wave 36 verified live Bambu CLI slicing for PrintPipe-generated full-settings `.3mf` bundles; physical slipper printing stays under Phase 16 beta/physical validation.

## Wave 29 - Physical Evidence Packets

Status: partial for F9. Evidence capture is implemented and tested, but the real PLA, PETG, and TPU physical prints remain user/printer-side work.

1. Done: added `printpipe.beta.physical` for structured physical print evidence packets.
2. Done: added JSON-friendly artifact and evidence serialization for coupon and small-object print results.
3. Done: added material-specific missing-evidence checks for TPU, PLA, and PETG.
4. Done: added Markdown rendering with required evidence headings and open-issue reporting.
5. Done: updated beta onboarding and slipper dogfood docs to require physical evidence packets for real print claims.
6. Remaining: print one PLA, one PETG, and one TPU coupon or small object, attach photos/notes, and keep F9 partial until those artifacts exist.

## Wave 30 - macOS Package Smoke Path

Status: complete for F10. This proves a clean macOS package smoke path around the `printpipe` entry point, not a signed/notarized app bundle.

1. Done: added `printpipe.packaging.smoke` with a clean-environment macOS smoke plan.
2. Done: added a generated ASCII STL fixture so the smoke path does not rely on repo test fixtures.
3. Done: added `printpipe package-smoke --platform macos --runs-dir ... --json`.
4. Done: the smoke command runs the real existing-mesh pipeline and records run root, reports, bundle paths, and slice-gate status.
5. Done: updated `docs/PACKAGING.md` and `docs/APP_ROADMAP.md` with the F10 boundary.
6. Remaining: original item 121 stays partial until there is a signed/notarized macOS app or installer flow.

## Wave 31 - Windows Package Smoke Path

Status: superseded by Wave 33. This wave added the Windows smoke command and PowerShell-ready plan; Wave 33 then executed it on a real Windows host.

1. Done: added Windows package smoke plan output alongside the macOS smoke path.
2. Done: added `printpipe package-smoke --platform windows --runs-dir ... --json`.
3. Done: non-Windows hosts return `manual_required` with the exact command to run on Windows instead of pretending the smoke passed.
4. Done: the Windows implementation can run the same generated-STL pipeline when invoked on a real Windows runtime.
5. Done: updated `docs/PACKAGING.md` and `docs/APP_ROADMAP.md` with the F11 boundary.
6. Superseded: real Windows execution evidence is now recorded in Wave 33.

## Wave 32 - Bambu CLI SIGSEGV Boundary

Status: superseded by Wave 36. This wave classified and documented the Bambu CLI/runtime crash boundary; Wave 36 then found the supported non-crashing PrintPipe path.

1. Done: recorded current host facts: Bambu Studio `02.06.00.51`, macOS `26.5`, build `25F71`.
2. Done: added `diagnose_bambu_cli_crash()` for known process-crash signatures.
3. Done: slice receipts now include structured diagnosis for signal crashes such as `SIGSEGV`.
4. Done: crash-report text containing `update_values_to_printer_extruders_for_multiple_filaments` is classified as `extruder_filament_mapping`.
5. Done: added `docs/research/wave32_bambu_cli_sigsegv.md` with the current boundary and workaround.
6. Superseded: Wave 36 found that sparse/direct inputs fail or crash, while full-settings Bambu-native `.3mf` bundles slice successfully.

## Wave 33 - Windows Package Smoke Evidence

Status: complete for F11. The Windows package smoke path has real Windows execution evidence, but original item 122 remains partial until there is a signed installer/package flow.

1. Done: verified `desktop-zt` is reachable over SSH.
2. Done: exported the current committed source with `git archive` because Windows GitHub auth was not configured.
3. Done: ran `printpipe package-smoke --platform windows --runs-dir runs/package-smoke/windows --json` on Windows through the temporary source export.
4. Done: Windows returned `status=ok`, with generated input fixture, reports, run root, and `.3mf` bundle.
5. Done: recorded the evidence in `docs/research/wave33_windows_package_smoke.md`.
6. Remaining: signed installer packaging and live Windows Bambu CLI slicing are separate future gates.

## Wave 34 - Physical Evidence CLI

Status: partial for F9. PrintPipe can now write physical evidence packets into run folders, but the real PLA, PETG, and TPU physical prints remain user/printer-side work.

1. Done: added `write_physical_evidence_files()` to write JSON and Markdown evidence under `90_physical/`.
2. Done: added `printpipe record-physical-evidence`.
3. Done: the command records material, printer, object label, print type/status, operator, drying, first-layer, adhesion, warping, stringing, layer-bonding, flex, support-removal, and notes.
4. Done: the command reports missing required evidence, so `not_printed` and incomplete coupon records stay honest.
5. Done: updated beta onboarding with the command and output paths.
6. Remaining: run real PLA, PETG, and TPU coupon/small-object prints and attach photos/notes before marking F9 complete.

## Wave 35 - Physical Evidence UI Surfacing

Status: partial for F9. Evidence capture is now visible in the product, but only real printer-side PLA/PETG/TPU prints can complete the physical validation gate.

1. Done: extended `printpipe record-physical-evidence` with repeatable `--photo` and `--artifact` inputs.
2. Done: copied evidence files into `90_physical/artifacts/` so packets are portable inside the run folder.
3. Done: loaded `90_physical/physical_evidence.json` in the run-detail contract with missing-evidence checks.
4. Done: surfaced recorded physical evidence, packet links, and photo/artifact links in the run-detail workbench.
5. Done: kept the UI honest: digital flex-coupon artifacts remain separate from physical coupon proof.
6. Remaining: run real PLA, PETG, and TPU coupon/small-object prints, then attach photos/notes before marking F9 complete.

## Wave 36 - Bambu CLI Full-Settings Slice Gate

Status: complete for F13 and original item 90. PrintPipe-generated `.3mf` bundles now carry the full resolved Bambu project settings needed by Bambu Studio CLI.

1. Done: reproduced the red regression that TPU bundles were missing inherited machine/process/filament keys such as `printable_area`.
2. Done: traced the root cause to sparse `Metadata/project_settings.config` output; the old known-good slipper bundle had 454 settings, while PrintPipe bundles had only the custom overrides.
3. Done: resolved Bambu/Orca profile inheritance from discovered profile roots and embedded machine, process, and filament defaults before applying SUNLU TPU 90A overrides.
4. Done: verified a fresh SUNLU TPU 90A `printpipe run ... --slice` command against Bambu Studio `02.06.00.51` on macOS `26.5` returned code 0, wrote `plate_1.gcode`, and reported zero warnings/errors.
5. Done: documented that raw direct-STL CLI slicing can still crash because it lacks project filament/profile context; PrintPipe's supported slice path is Bambu-native `.3mf`.
6. Remaining: physical PLA/PETG/TPU validation and signed packaging are still separate gates; live Windows Bambu CLI slicing is useful evidence later, not required for F13.

## Wave 37 - Run Detail 3MF Download Affordance

Status: complete for original item 120. The run-detail workbench now exposes the Bambu bundle as a browser-downloadable `.3mf` artifact.

1. Done: added a regression asserting the run-detail workbench renders `download="<bundle>.3mf"` for the bundle tile.
2. Done: kept download behavior limited to Bambu bundle artifacts with `category=bundle`, `.3mf` filename, and `model/3mf` media type.
3. Done: preserved the existing safe artifact-serving route and open-folder actions.
4. Done: updated the roadmap count to 125 done / 17 partial.
5. Remaining: signed packaging and real physical beta print evidence are still separate gates.

## Wave 38 - Inverted Normal Detection

Status: complete for original item 54. Mesh validation can now distinguish globally inverted closed-shell normals from inconsistent winding.

1. Done: added coordinate-aware validation for signed mesh volume when vertex coordinates are supplied.
2. Done: closed shells with consistent but inward-facing normals now fail with `inverted normals`.
3. Done: outward closed shells report `normal_orientation=outward` and pass.
4. Done: JSON gate output now records `normal_orientation`, `inverted_normals`, and `signed_volume`.
5. Done: updated the roadmap count to 126 done / 16 partial.
6. Remaining: media frame ranking/background cleanup, material physical prints, packaging, and beta loops remain separate gates.

## Wave 39 - Representative Frame Ranking

Status: complete for original item 39. Media reference selection no longer blindly takes the first frames.

1. Done: selected GIF/video references now spread across the extracted candidate set.
2. Done: selected-reference metadata records `selection_strategy=representative_frame_spread`, source frame index, and candidate count.
3. Done: selection receipts record the strategy and selected source frame indices.
4. Done: added regression coverage for 5 extracted frames -> selected frames 1, 3, and 5.
5. Done: updated the roadmap count to 127 done / 15 partial.
6. Remaining: background removal and lighting normalization are still honest no-op/copy stages until a real local or provider-backed implementation lands.

## Wave 40 - Configurable Media Cleanup Commands

Status: complete for original items 40 and 41. Background removal and lighting normalization can now run configured local/provider commands with receipts.

1. Done: added `PRINTPIPE_BACKGROUND_REMOVAL_COMMAND` support using `{input}` and `{output}` placeholders.
2. Done: added `PRINTPIPE_LIGHTING_NORMALIZATION_COMMAND` support using the same placeholder contract.
3. Done: cleanup metadata records whether semantic background removal and lighting normalization actually ran.
4. Done: cleanup receipts record `command_configured`, operation, and frame counts.
5. Done: no configured command still yields honest no-op/copy receipts instead of pretending.
6. Done: updated the roadmap count to 129 done / 13 partial.

## Wave 41 - PLA/PETG Material Bundle Dogfood

Status: complete for original items 109, 110, and 111 as software/slice tests. Physical material validation remains tracked under F9.

1. Done: added regression tests proving PLA/PLA+ material rules are merged into generated Bambu `.3mf` project settings instead of only changing the material label.
2. Done: added regression tests proving PETG material rules use the Generic PETG profile intent, PETG temperatures/MVS/brim settings, and `curr_bed_type=Textured PEI Plate`.
3. Done: wired PLA and PETG material overrides into the same full-settings bundle path used by TPU.
4. Done: reproduced the live PETG Bambu CLI failure `Plate 1: Cool Plate does not support filament 1`, then fixed it by carrying the PETG bed-type setting into the bundle.
5. Done: live-sliced tiny-tetrahedron PLA and PETG PrintPipe bundles with Bambu Studio `02.06.00.51` on macOS; both returned code 0, wrote G-code, and reported zero warnings/errors.
6. Done: updated the roadmap count to 132 done / 10 partial.

## Wave 42 - Engineering Material Bundle Coverage

Status: complete as software/slice coverage for ABS, ASA, PC, PA, and PA-CF. Physical validation remains tracked under F9/beta.

1. Done: added regression tests proving ABS, ASA, PC, PA, and PA-CF material requests no longer fall through to Generic PLA in generated `.3mf` bundles.
2. Done: wired ABS/ASA and PC/PA/PA-CF rule modules into the full-settings Bambu bundle path.
3. Done: added `curr_bed_type=Textured PEI Plate` to high-temperature/engineering material rules so Bambu does not default them to Cool Plate.
4. Done: live-sliced tiny-tetrahedron ABS, ASA, PC, PA, and PA-CF bundles with Bambu Studio `02.06.00.51` on macOS; all returned code 0, wrote G-code, and reported zero warnings/errors.
5. Boundary: this is software/slicer evidence only; real material-rule hardening still needs physical failed/successful prints through beta evidence packets.
6. Roadmap count remains 132 done / 10 partial because the remaining beta and packaging items are still physical/user/installer gates.

## Wave 43 - Portable Zipapp Package Artifact

Status: partial progress for original items 121 and 122. PrintPipe now has a real portable Python artifact, but not signed OS-native installers.

1. Done: added `printpipe.packaging.zipapp.build_zipapp_package()`.
2. Done: added `printpipe build-zipapp --output dist/printpipe.pyz`.
3. Done: verified the generated `.pyz` runs `--version` through `python printpipe.pyz`.
4. Done: verified the generated `.pyz` can run `package-smoke --platform macos` and produce reports plus a Bambu `.3mf`.
5. Done: removed stale package-smoke wording that still described the old Bambu CLI segfault boundary.
6. Remaining: signed/notarized macOS app, signed Windows installer, bundled Python runtime, shell shortcuts, and launcher/file-association polish remain separate packaging gates.

## Wave 44 - Windows Zipapp Artifact Smoke

Status: partial progress for original item 122. The portable zipapp artifact runs on Windows, but this is still not a signed installer.

1. Done: verified `desktop-zt` was reachable over SSH with Python `3.13.7` and PowerShell `5.1.26100.8521`.
2. Done: copied the generated `printpipe.pyz` artifact to `%TEMP%\printpipe-zipapp\printpipe.pyz`.
3. Done: ran `python %TEMP%\printpipe-zipapp\printpipe.pyz --version` on Windows and got `printpipe 0.1.0`.
4. Done: ran `python %TEMP%\printpipe-zipapp\printpipe.pyz package-smoke --platform windows --runs-dir %TEMP%\printpipe-zipapp\runs --json`.
5. Done: Windows zipapp smoke returned `status=ok`, `windows_runtime=ok`, report artifacts, and `existing_stl_package_smoke_tiny_tetrahedron.3mf`.
6. Remaining: signed Windows installer, bundled runtime, Start Menu/shortcut integration, and live Windows+Bambu Studio slice check are still separate gates.

## Wave 45 - Windows Bambu CLI Boundary Check

Status: boundary recorded for Windows live slicing. Packaging artifact smoke passed; Windows+Bambu slicing is waiting on an installed Bambu Studio path.

1. Done: checked common Windows install candidates under Program Files and LocalAppData for Bambu Studio.
2. Done: ran a broader PowerShell search for `BambuStudio.exe`.
3. Result: no Bambu Studio executable was found on `desktop-zt`.
4. Boundary: Windows live Bambu CLI slicing cannot be verified on that host until Bambu Studio is installed or an explicit path is provided.
5. Current evidence still stands: the same `printpipe.pyz` artifact runs on Windows and creates reports plus a `.3mf`.
6. Remaining: signed installer and Windows+Bambu slice evidence stay open packaging gates.

## Wave 46 - Unsigned macOS App Bundle

Status: partial progress for original item 121. PrintPipe now builds a launchable `.app` wrapper, but it is unsigned and not notarized.

1. Done: added `printpipe.packaging.macos_app.build_macos_app_bundle()`.
2. Done: added `printpipe build-macos-app --output dist/PrintPipe.app`.
3. Done: the app bundle embeds `Contents/Resources/printpipe.pyz`, writes `Contents/Info.plist`, and exposes `Contents/MacOS/printpipe`.
4. Done: verified `Contents/MacOS/printpipe --version` returns `printpipe 0.1.0`.
5. Done: verified the app-bundle launcher can run `package-smoke --platform macos`, returning `status=ok` with reports and a Bambu `.3mf`.
6. Remaining: signing, notarization, bundled Python runtime, and polished double-click GUI/launcher behavior are separate gates.

## Wave 47 - Ad-Hoc macOS App Signing

Status: partial progress for original item 121. The app bundle can now be locally ad-hoc signed, but it is not Developer ID signed or notarized.

1. Done: added `adhoc_sign=True` to `build_macos_app_bundle()`.
2. Done: added `printpipe build-macos-app --adhoc-sign`.
3. Done: live-built an app with `signed=true`, `signing_identity="-"`, and `notarized=false`.
4. Done: verified `codesign --verify --deep --strict PrintPipe.app` returned `0`.
5. Done: verified the signed app launcher still returns `printpipe 0.1.0`.
6. Remaining: Developer ID signing, notarization, bundled runtime, and release packaging stay open.

## Wave 48 - macOS App Web Launcher

Status: partial progress for original item 121. The `.app` bundle now has a useful default launch path, but it is still not a signed/notarized native installer.

1. Done: changed the no-argument app launcher path to start `printpipe serve`.
2. Done: the default URL is `http://127.0.0.1:8765/`.
3. Done: the default app-run folder is `~/PrintPipe/runs`, avoiding accidental `/runs` writes from Finder launch context.
4. Done: the launcher opens the local URL after startup while preserving CLI pass-through for `--version` and `package-smoke`.
5. Done: added `PRINTPIPE_APP_DRY_RUN=1` smoke coverage for the no-arg launcher path.
6. Remaining: Developer ID signing, notarization, bundled Python runtime, file associations, and release installer packaging stay open.

## Wave 49 - macOS App Document Launch

Status: partial progress for original item 121. The `.app` bundle now declares and handles supported input documents, but it still does not install itself as the default handler and is not a signed/notarized installer.

1. Done: added `CFBundleDocumentTypes` for mesh/media input extensions.
2. Done: added a one-file launcher branch that runs `printpipe run <file>` into `~/PrintPipe/runs`.
3. Done: after document processing, the launcher starts the local web UI at `http://127.0.0.1:8765/`.
4. Done: preserved CLI pass-through for normal subcommands and flags.
5. Done: added `PRINTPIPE_APP_DRY_RUN=1` smoke coverage for the document-launch path.
6. Remaining: default-handler registration, Developer ID signing, notarization, bundled Python runtime, and release installer packaging stay open.

## Wave 50 - macOS DMG Distribution Artifact

Status: partial progress for original item 121. PrintPipe can now produce a real drag-install `.dmg`, but it is still not Developer ID signed, notarized, or runtime-bundled.

1. Done: added `printpipe.packaging.macos_dmg.build_macos_dmg_package()`.
2. Done: added `printpipe build-macos-dmg --output dist/PrintPipe.dmg`.
3. Done: the DMG staging folder contains `PrintPipe.app` and an `Applications` symlink.
4. Done: the DMG builder uses `hdiutil create -format UDZO`.
5. Done: verified the generated artifact with `hdiutil imageinfo`.
6. Remaining: Developer ID signing, notarization, bundled Python runtime, default-handler registration, and Windows signed installer packaging stay open.

## Wave 51 - Windows Portable ZIP Artifact

Status: partial progress for original item 122. PrintPipe now has a Windows-friendly portable ZIP handoff, but it is still not a signed installer and does not bundle Python.

1. Done: added `printpipe.packaging.windows_portable.build_windows_portable_package()`.
2. Done: added `printpipe build-windows-portable --output dist/PrintPipe-Windows-portable.zip`.
3. Done: the ZIP contains `PrintPipe/printpipe.pyz`.
4. Done: the ZIP contains `PrintPipe/printpipe.cmd` and `PrintPipe/printpipe.ps1` launchers.
5. Done: verified the portable ZIP on `desktop-zt`: `.cmd` and `.ps1` returned `printpipe 0.1.0`, and `.cmd package-smoke --platform windows` returned `status=ok` with reports plus a `.3mf`.
6. Remaining: signed Windows installer, bundled Python runtime, Start Menu shortcuts, file association registration, and live Windows+Bambu slice evidence stay open.

## Wave 52 - Windows Start Menu Shortcut Scripts

Status: partial progress for original item 122. The portable ZIP now includes reversible user-scope Start Menu shortcut scripts, but it is still not a signed Windows installer.

1. Done: added `PrintPipe/install-start-menu.ps1` to the portable ZIP.
2. Done: added `PrintPipe/uninstall-start-menu.ps1` to the portable ZIP.
3. Done: the installer creates `%APPDATA%\Microsoft\Windows\Start Menu\Programs\PrintPipe\PrintPipe CLI.lnk`.
4. Done: the shortcut opens `printpipe.cmd` in a persistent Command Prompt.
5. Done: verified on `desktop-zt` that install created `PrintPipe CLI.lnk` and uninstall removed it.
6. Remaining: signed Windows installer, bundled Python runtime, file association registration, and live Windows+Bambu slice evidence stay open.

## Wave 53 - Windows File Association Scripts

Status: partial progress for original item 122. The portable ZIP now includes reversible user-scope file association scripts, but it is still not a signed Windows installer.

1. Done: added `PrintPipe/install-file-associations.ps1` to the portable ZIP.
2. Done: added `PrintPipe/uninstall-file-associations.ps1` to the portable ZIP.
3. Done: default extensions are `.stl`, `.obj`, `.3mf`, `.glb`, and `.gltf`.
4. Done: installer skips existing handlers unless `-Force` is passed.
5. Done: verified on `desktop-zt` with a throwaway `.printpipetest` extension; install created an HKCU association and uninstall removed it.
6. Remaining: signed Windows installer, bundled Python runtime, and live Windows+Bambu slice evidence stay open.

## Wave 54 - Release Bundle Manifest

Status: partial progress for original items 121 and 122. PrintPipe can now build a single local release folder with checksummed handoff artifacts, but the artifacts still carry the signed-installer/runtime/physical boundaries.

1. Done: added `printpipe.packaging.release.build_release_bundle()`.
2. Done: added `printpipe build-release --output-dir dist/release`.
3. Done: release output includes `printpipe.pyz`, `PrintPipe.dmg`, and `PrintPipe-Windows-portable.zip`.
4. Done: release output includes `release_manifest.json`.
5. Done: manifest records `sha256`, size, signing/notarization, Python-runtime, and Bambu-bundling metadata per artifact.
6. Remaining: Developer ID notarization, signed Windows installer, bundled Python runtime, live Windows+Bambu slice evidence, and physical print validation stay open.

## Wave 55 - Release Bundle Verifier

Status: partial progress for original items 121 and 122. PrintPipe can now verify that a release handoff folder still matches its manifest before sharing or archiving it.

1. Done: added `printpipe.packaging.release.verify_release_bundle()`.
2. Done: added `printpipe verify-release dist/release --json`.
3. Done: verifier checks `release_manifest.json` exists and parses as JSON.
4. Done: verifier checks release boundary claims match current PrintPipe boundary text.
5. Done: verifier checks every manifest artifact exists, stays inside the release folder, and matches recorded size plus SHA-256.
6. Done: verifier exits `0` for intact folders and `2` for failed verification.
7. Remaining: Developer ID notarization, signed Windows installer, bundled Python runtime, live Windows+Bambu slice evidence, and physical print validation stay open.

## Wave 56 - macOS Signing Readiness Doctor

Status: partial progress for original item 121. PrintPipe now distinguishes local packaging/tool readiness from the missing Apple Developer signing credential gate.

1. Done: added `printpipe.env.macos.macos_signing_readiness()`.
2. Done: readiness checks `codesign`, `productbuild`, `security`, and `notarytool`.
3. Done: readiness parses `security find-identity -v -p codesigning` for `Developer ID Application` and `Developer ID Installer` identities.
4. Done: `printpipe doctor` now renders macOS signing status and missing tools/identities.
5. Done: `printpipe doctor --json` includes the signing readiness packet under `system.signing`.
6. Boundary on this Mac: signing tools are present, but no valid Developer ID identities are installed.
7. Remaining: install Apple Developer certificates, perform real Developer ID signing/notarization, signed Windows installer, bundled Python runtime, live Windows+Bambu slice evidence, and physical print validation stay open.

## Wave 57 - macOS Standalone Runtime App

Status: partial progress for original item 121. PrintPipe can now build a macOS `.app` that includes a Python runtime through PyInstaller, but it is not Developer ID signed/notarized and is not yet the default release artifact.

1. Done: added `printpipe.packaging.macos_standalone.build_macos_standalone_app()`.
2. Done: added `printpipe build-macos-standalone --output dist/PrintPipeStandalone.app`.
3. Done: standalone entrypoint preserves CLI passthrough, no-arg local web UI launch, and one-file document launch behavior.
4. Done: generated app metadata includes alternate document types for supported mesh/media inputs.
5. Done: live-built with `uvx --from pyinstaller pyinstaller`; resulting app reported `bundles_python_runtime=true`.
6. Done: live executable returned `printpipe 0.1.0`; dry-run launch printed the `http://127.0.0.1:8765/` local web UI command.
7. Remaining: Developer ID signing/notarization, making the standalone app part of the release bundle, signed Windows installer, Windows bundled runtime, live Windows+Bambu slice evidence, and physical print validation stay open.

## Wave 58 - Optional Standalone Release Artifact

Status: partial progress for original item 121. The release folder can now opt into carrying the runtime-bundled macOS app as a zipped artifact, while the default release remains lightweight.

1. Done: added `build_release_bundle(include_standalone=True, pyinstaller_command=...)`.
2. Done: added `printpipe build-release --include-standalone --pyinstaller ...`.
3. Done: release output includes `PrintPipeStandalone-macOS.zip` when standalone inclusion is requested.
4. Done: manifest records the standalone artifact as `macos_standalone_zip` with `bundles_python_runtime=true`.
5. Done: release boundary text changes when a Python-runtime artifact is present.
6. Done: `printpipe verify-release` validates both default and standalone-including release manifests.
7. Remaining: Developer ID signing/notarization, signed Windows installer, Windows bundled runtime, live Windows+Bambu slice evidence, and physical print validation stay open.

## Wave 59 - Windows Standalone Runtime ZIP

Status: partial progress for original item 122. PrintPipe can now build and run a Windows ZIP that bundles its Python runtime, but it is still not a signed Windows installer and does not bundle Bambu Studio.

1. Done: added `printpipe.packaging.windows_standalone.build_windows_standalone_package()`.
2. Done: added `printpipe build-windows-standalone --output dist/PrintPipe-Windows-standalone.zip`.
3. Done: the ZIP contains `PrintPipe/PrintPipe.exe`, PyInstaller `_internal` runtime files, and `PrintPipe/README.txt`.
4. Done: standalone entrypoint preserves CLI passthrough and a no-arg local web UI launch path.
5. Done: live-built on `desktop-zt`; metadata reported `bundles_python_runtime=true`, `bundles_bambu_studio=false`, and `signed=false`.
6. Done: extracted `PrintPipe.exe --version` returned `printpipe 0.1.0`; dry-run launch printed the `http://127.0.0.1:8765/` local web UI command.
7. Done: extracted `PrintPipe.exe package-smoke --platform windows ... --json` returned `status=ok` with reports and a Bambu `.3mf`.
8. Remaining: signed Windows installer, Start Menu/file-association integration for the standalone executable, live Windows+Bambu slice evidence, Developer ID notarization, and physical print validation stay open.

## Wave 60 - Release Bundle Windows Standalone Inclusion

Status: partial progress for original item 122. The release folder can now carry the prebuilt Windows standalone runtime ZIP as a checksummed manifest artifact, but the ZIP is still not a signed Windows installer.

1. Done: added `windows_standalone_zip` support to `build_release_bundle()`.
2. Done: added `printpipe build-release --windows-standalone-zip dist/PrintPipe-Windows-standalone.zip`.
3. Done: release building copies the prebuilt ZIP to `PrintPipe-Windows-standalone.zip` inside the release folder.
4. Done: release building validates that the ZIP contains `PrintPipe/PrintPipe.exe` and bundled Python runtime files before manifesting it.
5. Done: manifest records the copied artifact as `windows_standalone_zip` with `bundles_python_runtime=true`, `bundles_bambu_studio=false`, `signed=false`, and `notarized=false`.
6. Done: release boundary text distinguishes macOS-only, Windows-only, and combined standalone-runtime release shapes.
7. Remaining: signed Windows installer, live Windows+Bambu slice evidence, Developer ID notarization, and physical print validation stay open.

## Wave 61 - Windows Standalone Helper Scripts

Status: partial progress for original item 122. The Windows standalone runtime ZIP now includes reversible user-scope convenience scripts, but it remains unsigned and is not a native installer.

1. Done: added `install-start-menu.ps1` and `uninstall-start-menu.ps1` to `PrintPipe-Windows-standalone.zip`.
2. Done: added `install-file-associations.ps1` and `uninstall-file-associations.ps1` to `PrintPipe-Windows-standalone.zip`.
3. Done: the Start Menu script creates `PrintPipe.lnk` pointing directly at `PrintPipe.exe`.
4. Done: file associations run `"PrintPipe.exe" "%1"` so the standalone one-file document launcher processes the input and opens the local UI.
5. Done: live-verified on `desktop-zt` that the shortcut installs and uninstalls cleanly.
6. Done: live-verified a throwaway `.printpipestandtest` HKCU association installs with the expected command and uninstalls cleanly.
7. Done: rebuilt standalone `PrintPipe.exe package-smoke --platform windows ... --json` returned `status=ok` with reports and a Bambu `.3mf`.
8. Remaining: signed Windows installer, live Windows+Bambu slice evidence, Developer ID notarization, and physical print validation stay open.

## Wave 62 - Windows Installer Signing Readiness Doctor

Status: partial progress for original item 122. PrintPipe now reports whether a Windows host is ready to build/sign a native installer, but the required signing tools and certificate are not present on `desktop-zt`.

1. Done: added `printpipe.env.windows.windows_installer_signing_readiness()`.
2. Done: readiness checks for `signtool`, `powershell`, and at least one installer tool from `wix/iscc/makensis`.
3. Done: readiness queries `Cert:\CurrentUser\My -CodeSigningCert` for code-signing certificate subjects.
4. Done: `printpipe doctor --json` includes the packet under `system.signing` on Windows.
5. Done: human doctor output labels the section `Windows installer signing` instead of macOS signing on Windows reports.
6. Boundary on `desktop-zt`: PowerShell is present, but `signtool`, `wix/iscc/makensis`, and a `Code Signing Certificate` are missing; status is `missing_tools`.
7. Remaining: install Windows signing/installer tools and certificate, build a signed native installer, install Bambu Studio on Windows for live slice evidence, complete physical print validation.

## Wave 63 - Prompt-Only CLI Input Path

Status: partial progress for prompt/reference generation. Prompt-only and prompt-plus-reference are now wired through the CLI, but the local web UI still needs a matching prompt field.

1. Done: added `InputKind.PROMPT` and prompt run manifests with `00_input/prompt.txt`.
2. Done: added `printpipe run --prompt "..."` for prompt-only runs.
3. Done: added `PRINTPIPE_PROMPT_IMAGE_COMMAND`, requiring `{prompt_file}` and `{output}`, to generate a concrete prompt reference image.
4. Done: missing prompt-image command now fails at `prompt_reference_generation` with run reports instead of pretending prompt-only geometry exists.
5. Done: configured prompt-image command output flows through reference cleanup/selection/contact sheet, then into Hunyuan3D as an image reference.
6. Done: `printpipe run image.png --prompt "..."` passes the prompt through to meshgen providers as `prompt_hint`.
7. Done: CLI tests cover both missing-command failure and configured prompt-image-plus-Hunyuan success into a Bambu `.3mf`.
8. Remaining: local web UI prompt input, real prompt-image model adapter, hosted/image-provider selection UI, and physical validation stay open.

## Wave 64 - Local Web Prompt Input

Status: partial progress for prompt/reference generation. The local web UI now matches the CLI input modes for prompt-only and prompt-plus-file runs, while real prompt-image provider selection remains future work.

1. Done: added a `Prompt` field to the local web new-run form.
2. Done: web prompt-only submissions write `00_input/prompt.txt` and a prompt manifest.
3. Done: prompt-only web runs call the same `PRINTPIPE_PROMPT_IMAGE_COMMAND` spine as `printpipe run --prompt`.
4. Done: missing prompt-image command fails honestly at `prompt_reference_generation` with reports and warnings.
5. Done: file-plus-prompt web runs preserve the prompt in `manifest.json` launch options and pass it to meshgen as `prompt_hint`.
6. Done: launch metadata now records `input_mode` as `file`, `prompt`, or `file+prompt`.
7. Remaining: real prompt-image model adapter, hosted/local provider selection UI, and physical validation stay open.

## Wave 65 - Prompt Image Provider Selection

Status: partial progress for prompt/reference generation. Prompt-only runs now have a provider-aware reference image layer instead of only a raw command hook, but physical validation remains outside software.

1. Done: added explicit prompt-image provider resolution for `auto`, `command`, and `openai`.
2. Done: preserved `PRINTPIPE_PROMPT_IMAGE_COMMAND` as the command provider and as the first `auto` choice.
3. Done: added an OpenAI Images API prompt-image adapter using `OPENAI_API_KEY`.
4. Done: OpenAI model, size, quality, background, output format, and base URL are configurable through env vars.
5. Done: failed prompt-image setup now records provider-specific receipts instead of a generic command-only failure.
6. Done: added `printpipe run --prompt-image-provider auto|command|openai`.
7. Done: added a local web `Prompt image provider` selector and persisted the selected provider in launch metadata.
8. Remaining: real live OpenAI/API-key run evidence, hosted cost/quality policy, and physical validation stay open.

## Wave 66 - Prompt Image Quote and Budget Receipts

Status: partial progress for hosted/provider safety. Prompt-image runs now record cost/privacy/latency quote metadata and enforce a fail-closed cost cap before remote API calls.

1. Done: command prompt-image provider records a local/user-configured zero-cost quote.
2. Done: OpenAI prompt-image provider records remote API privacy mode, estimated latency, estimated cost, and max-cost metadata.
3. Done: OpenAI estimated cost is user-configured through `PRINTPIPE_OPENAI_IMAGE_ESTIMATED_COST_USD`, not hardcoded as a pricing promise.
4. Done: `PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD` fails before the API call when the estimate is missing.
5. Done: `PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD` fails before the API call when the estimate exceeds the cap.
6. Done: CLI reports and run reports include the provider quote metadata on blocked cost-cap runs.
7. Remaining: real live OpenAI/API-key evidence, provider quality comparison, and physical validation stay open.

## Wave 67 - Prompt Provider Receipts in Run Detail

Status: partial progress for prompt/reference trust. The workbench now exposes prompt-provider quote/budget receipts and no longer hides prompt-reference failures behind successful input classification.

1. Done: added a `prompt_reference` run-detail contract slice from `prompt_reference_generation` stage metrics.
2. Done: surfaced provider, privacy mode, estimated cost, max cost, latency, remote-upload note, and budget status in the run-detail UI.
3. Done: `Input / reference` now summarizes all matching input/reference receipts and fails if any matching receipt failed.
4. Done: prompt-reference failures now block the top-level print verdict instead of leaving the run in a generic review state.
5. Done: regression coverage proves an OpenAI cost-cap failure is visible in both the contract and workbench.
6. Remaining: real live OpenAI/API-key evidence, provider quality comparison, and physical validation stay open.

## Wave 68 - Prompt Provider Receipts in Static Reports

Status: partial progress for prompt/reference evidence portability. Prompt-provider quote/budget receipts now appear in the Markdown and HTML run reports, not only the live workbench.

1. Done: Markdown reports add a `Prompt Reference` section when `prompt_reference_generation` receipts exist.
2. Done: HTML reports add a `Prompt Reference` section with provider, status, privacy mode, estimated cost, max cost, latency, budget status, and remote prompt-storage note.
3. Done: report tests prove OpenAI cost-cap failure receipts are promoted instead of buried inside raw stage metrics.
4. Done: report CSS keeps the prompt-reference receipt readable on desktop and mobile report layouts.
5. Remaining: real live OpenAI/API-key evidence, provider quality comparison, and physical validation stay open.

## Wave 69 - Report Empty-State Honesty

Status: complete for report-copy cleanup. Static Markdown and HTML reports no longer imply that slice/preflight systems are globally unfinished when a specific report simply has no slice or checklist receipt.

1. Done: replaced Markdown pre-print empty copy with `No pre-print checklist recorded for this report.`
2. Done: replaced HTML slice empty copy with `No slice receipt recorded for this report.`
3. Done: replaced HTML pre-print empty copy with `No pre-print checklist recorded for this report.`
4. Done: added regression coverage that rejects the stale `pending final slice gate integration` wording.
5. Boundary: this does not create slice receipts, checklist items, or physical print evidence; it only keeps missing evidence language accurate.

## Wave 70 - Physical Evidence in Static Reports

Status: complete for evidence portability. Physical print evidence packets now surface in the static JSON, Markdown, and HTML run reports when a packet is recorded.

1. Done: `build_run_report_dict()` and `write_run_report()` accept optional `physical_evidence`.
2. Done: Markdown reports render a `Physical Evidence` section with status, object, operator, material, printer, packet links, artifact links, and missing-evidence summary.
3. Done: HTML reports render a `Physical Evidence` section with the same evidence packet and artifact links.
4. Done: `printpipe record-physical-evidence` refreshes existing `80_reports/run_report.json`, `.md`, and `.html` when a run report already exists.
5. Boundary: recording evidence still does not upgrade a run to physically validated unless the packet itself contains credible real print status and required evidence.

## Wave 71 - Physical Validation Status Scanner

Status: complete for beta-gate visibility. PrintPipe can now scan run folders and say whether the required PLA/PETG/TPU physical evidence has actually passed.

1. Done: added `printpipe.beta.physical_status.build_physical_validation_status()`.
2. Done: scanner reads `90_physical/physical_evidence.json` packets across a `runs/` directory.
3. Done: required material families default to PLA, PETG, and TPU.
4. Done: family status distinguishes `passed`, `missing`, `incomplete`, and `recorded_but_not_passed`.
5. Done: added `printpipe physical-status --runs-dir runs --json --strict`.
6. Done: strict mode exits `2` until every required family has a passed packet with no missing required evidence.
7. Boundary: this reports physical validation status; it does not create physical evidence or claim that unprinted coupons passed.

## Wave 72 - Physical Beta Gate in Local UI

Status: complete for local visibility. The home page now surfaces the same physical validation gate that the CLI exposes.

1. Done: local web home calls `build_physical_validation_status()` when a runs directory is configured.
2. Done: the page shows the overall physical gate status.
3. Done: the page shows PLA, PETG, and TPU cards with passed packet counts and missing reasons.
4. Done: the panel explicitly says digital artifacts do not count as physical proof.
5. Done: the panel shows the strict CLI command for beta/release gating.
6. Boundary: this is a read-only status panel; it does not record evidence, edit packets, or mark physical prints as passed.

## Wave 73 - Physical Validation JSON Endpoint

Status: complete for local app/API visibility. The physical validation gate is now machine-readable from the local web app.

1. Done: added `GET /physical-status.json`.
2. Done: endpoint returns the same `build_physical_validation_status()` payload used by the CLI and home page.
3. Done: endpoint returns `503` when the web app has no runs directory configured.
4. Done: regression coverage proves the endpoint reports passed PLA evidence while keeping missing PETG/TPU gates explicit.
5. Boundary: this is a read-only status endpoint; it does not mutate evidence packets or bypass the strict physical validation gate.

## Wave 74 - Environment Doctor JSON Endpoint

Status: complete for local app/API visibility. Environment, dependency, Bambu, filesystem, and signing readiness are now machine-readable from the local web app.

1. Done: added `GET /doctor.json`.
2. Done: endpoint returns the existing `build_environment_report()` payload used by `printpipe doctor --json`.
3. Done: home page service links now include `Environment doctor JSON`.
4. Done: regression coverage proves the endpoint returns Bambu/environment readiness data.
5. Boundary: this exposes readiness status only; it does not install dependencies, certificates, signing tools, Bambu Studio, or OS-native installers.

## Wave 75 - Combined Beta Readiness Report

Status: complete for gate visibility. PrintPipe now has one local readiness report that combines physical validation and environment/package prerequisites.

1. Done: added `printpipe.beta.readiness.build_beta_readiness_report()`.
2. Done: readiness gates cover physical validation, required dependencies, filesystem access, Bambu Studio, Bambu profile folders, and release signing.
3. Done: report returns `ready` only when all actionable gates are ready.
4. Done: added `GET /readiness.json`.
5. Done: home page service links now include `Readiness JSON`.
6. Boundary: this is a reporting layer; it does not print coupons, install tools, sign packages, or convert missing evidence into completion.

## Wave 76 - Readiness Gates on Home Page

Status: complete for local dashboard visibility. The combined readiness report now appears directly on the local home page.

1. Done: home page calls `build_beta_readiness_report()` when a runs directory is configured.
2. Done: the page shows overall readiness and action-required count.
3. Done: the page renders each readiness gate with status, detail, and action.
4. Done: regression coverage proves physical validation and release-signing blockers are visible without opening JSON.
5. Boundary: the panel is read-only; it does not complete physical prints or signing work.

## Wave 77 - Readiness CLI Command

Status: complete for terminal/release-script visibility. The combined readiness report now has CLI parity with the local web app.

1. Done: added `printpipe readiness --runs-dir runs`.
2. Done: added `--json` output for automation and release scripts.
3. Done: added `--strict`, returning exit code `2` unless all readiness gates are ready.
4. Done: added a concise human renderer for physical, dependency, Bambu, filesystem, and signing gates.
5. Done: regression coverage proves parser support, strict JSON gating, and human gate summaries.
6. Boundary: the command is read-only; it does not print physical coupons, install dependencies, or sign/notarize release artifacts.

## Wave 78 - macOS Developer ID Signing Plumbing

Status: partial progress for original item 121. PrintPipe now has real Developer ID signing and notarization command plumbing, but actual signing/notarization still requires Zohar's Apple Developer identities and a configured notary keychain profile.

1. Done: added `printpipe.packaging.macos_signing.sign_macos_path()` for Developer ID `codesign` plus verification.
2. Done: added `printpipe.packaging.macos_signing.notarize_macos_artifact()` for `xcrun notarytool submit --wait` plus `stapler`.
3. Done: `build-macos-app` accepts `--developer-id-identity`.
4. Done: `build-macos-dmg` accepts `--developer-id-identity` and `--notary-profile`.
5. Done: `build-release` can pass Developer ID/notary options into the release DMG and manifest the notarized boundary honestly.
6. Boundary: no certificate or notary profile was installed by this wave; the readiness gate remains action-required on this machine.

## Wave 79 - Windows Native Installer Plumbing

Status: partial progress for original item 122. PrintPipe now has native Windows installer build/sign command plumbing, but actual signed installer production still requires Windows installer tools plus a code-signing certificate.

1. Done: added `printpipe.packaging.windows_installer.build_windows_installer_package()`.
2. Done: the installer builder wraps `PrintPipe-Windows-standalone.zip` with Inno Setup.
3. Done: optional Authenticode signing uses `signtool sign /n ... /fd SHA256 /tr ... /td SHA256`.
4. Done: added `printpipe build-windows-installer --standalone-zip ... --output ...`.
5. Done: `build-release --windows-installer-exe ...` can copy a prebuilt signed installer into the checksummed release manifest.
6. Boundary: no Windows signing certificate, `signtool`, or Inno/WiX/NSIS installer tool was installed by this wave; the Windows readiness gate remains action-required on `desktop-zt`.

## Wave 80 - Release Verifier Metadata Hardening

Status: complete for release-trust hardening. `verify-release` now rejects internally inconsistent native-artifact metadata instead of only checking bytes and boundary text.

1. Done: added regression coverage for a `windows_installer` artifact that is present and hash-correct but carries `signed=false`.
2. Done: added regression coverage for a `windows_installer` artifact with a non-`.exe` path.
3. Done: added regression coverage for a `macos_dmg` artifact claiming `notarized=true` while `signed=false`.
4. Done: added type-specific verifier checks for zipapp, macOS DMG, macOS standalone ZIP, Windows portable ZIP, Windows standalone ZIP, and Windows installer artifacts.
5. Done: `verify-release` now reports explicit `artifact_metadata:*` failures alongside existence, size, SHA-256, and boundary checks.
6. Boundary: this hardens manifest verification; it does not create Apple Developer certificates, a notary profile, Windows signing tools, a Windows signing certificate, or physical print evidence.

## Wave 81 - Combined Release Status Command

Status: complete for release gate visibility. PrintPipe now has one terminal command that combines release-folder verification with beta/readiness gates and next actions.

1. Done: added `printpipe.packaging.release_status.build_release_status_report()`.
2. Done: the report starts with a `release_bundle` gate from `verify_release_bundle()`.
3. Done: the report appends the existing physical, dependency, Bambu, filesystem, and signing gates from `build_beta_readiness_report()`.
4. Done: added `printpipe release-status --release-dir dist/release --runs-dir runs`.
5. Done: added `--json` and `--strict`, returning exit code `2` unless release integrity and readiness gates are all ready.
6. Boundary: this is a read-only status layer; it does not build a release, sign packages, install tools, or record physical evidence.

## Wave 82 - Local Release Bundle Smoke Evidence

Status: partial progress for original items 121 and 122. A local ignored release bundle now verifies cleanly, while final distribution gates still require physical evidence and real signing credentials.

1. Done: ran `printpipe build-release --output-dir dist/release --adhoc-sign --json`.
2. Done: generated `printpipe.pyz`, `PrintPipe.dmg`, `PrintPipe-Windows-portable.zip`, and `release_manifest.json` in ignored `dist/release`.
3. Done: `printpipe verify-release dist/release --json` returned exit code `0` with all manifest, boundary, metadata, size, and SHA-256 checks passing.
4. Done: `printpipe release-status --release-dir dist/release --runs-dir runs --json --strict` reported the `release_bundle` gate as `ready`.
5. Remaining: `release-status --strict` still returns exit code `2` because PLA/PETG/TPU physical evidence is missing and Developer ID Application/Installer identities are not installed.
6. Boundary: generated files stay ignored under `dist/`; this wave records smoke evidence, not a committed binary release or final signed/notarized distribution.

## Wave 83 - Standalone Runtime Release Smoke Evidence

Status: partial progress for original item 121. The local release smoke now covers the macOS standalone runtime ZIP shape, not only the default zipapp/DMG/Windows-portable shape.

1. Done: ran `printpipe build-release --output-dir dist/release --adhoc-sign --include-standalone --pyinstaller "uvx --from pyinstaller pyinstaller" --json`.
2. Done: generated `PrintPipeStandalone-macOS.zip` in ignored `dist/release`.
3. Done: manifest records `macos_standalone_zip` with `bundles_python_runtime=true`, `bundles_bambu_studio=false`, and `signed=true`.
4. Done: `printpipe verify-release dist/release --json` returned exit code `0` across 4 artifacts.
5. Done: `printpipe release-status --release-dir dist/release --runs-dir runs --json --strict` reported the release bundle gate as `ready` with 4 verified artifacts.
6. Remaining: final macOS distribution still needs Developer ID signing/notarization; final beta/release still needs physical PLA/PETG/TPU evidence.

## Wave 84 - Release Distribution Gates

Status: complete for final-release gate visibility. `release-status` now distinguishes an intact release folder from a final signed Mac/Windows distribution.

1. Done: added `macos_distribution` gate to `printpipe release-status`.
2. Done: the macOS distribution gate only passes when the manifest records a `macos_dmg` with `signed=true` and `notarized=true`.
3. Done: added `windows_distribution` gate to `printpipe release-status`.
4. Done: the Windows distribution gate only passes when the manifest records a `windows_installer` with `signed=true`.
5. Done: release-status now reads release artifacts from injected verification payloads or from `release_manifest.json`.
6. Boundary: these gates report final distribution completeness; they do not create certificates, notarize a DMG, or sign a Windows installer.

## Wave 85 - Release Status in Local Web UI

Status: complete for local web parity. The stronger release-status gates are now visible in the browser, not only through the CLI.

1. Done: added `GET /release-status.json`.
2. Done: the endpoint returns `build_release_status_report(release_dir=..., runs_dir=...)`.
3. Done: added a home-page `Release status` panel before the older readiness panel.
4. Done: the panel renders release bundle, macOS distribution, Windows distribution, physical, dependency, Bambu, filesystem, and signing gates from the combined report.
5. Done: added `Release status JSON` to the home page service links.
6. Done: browser smoke on `http://127.0.0.1:8895/` showed `Release status`, `macOS distribution`, `Windows distribution`, and `Release status JSON`; `/release-status.json` returned the expected action-required gates.
7. Boundary: this is read-only UI visibility; it does not build releases, sign packages, install tools, or record physical evidence.

## Wave 86 - Physical Validation Action Plan

Status: complete for printer-side action planning. PrintPipe now turns the remaining PLA/PETG/TPU physical validation gate into exact next actions instead of only reporting missing evidence.

1. Done: added `printpipe.beta.physical_plan.build_physical_validation_plan()`.
2. Done: added `printpipe physical-plan --runs-dir runs` with JSON and human renderers.
3. Done: missing or incomplete PLA/PETG/TPU families produce family-specific `record-physical-evidence` command skeletons.
4. Done: the plan targets an existing incomplete packet's run folder when available, otherwise uses a clear placeholder run root for the next physical print.
5. Done: the plan repeats the proof boundary: generated coupons, digital artifacts, and slice receipts do not count as physical proof until a real print is recorded.
6. Boundary: this wave does not create fake physical evidence or mark F9 complete; real PLA, PETG, and TPU coupon/small-object prints are still required.

## Wave 87 - Physical Action Plan in Local Web UI

Status: complete for local web visibility. The browser now shows the same physical validation action plan as the CLI.

1. Done: added `GET /physical-plan.json`.
2. Done: added `Physical plan JSON` to the home-page service links.
3. Done: added a `Physical action plan` home panel below the physical beta gate.
4. Done: the panel renders missing/incomplete material-family actions, required fields, and exact `record-physical-evidence` command skeletons.
5. Done: the panel repeats the proof boundary so UI users do not confuse generated coupons or slice receipts with real print evidence.
6. Boundary: this is read-only guidance; it does not record evidence or mark physical validation complete.

## Wave 88 - Runnable Physical Plan Setup Commands

Status: complete for print-day command usability. Missing physical-validation families now get deterministic run folders instead of abstract placeholders.

1. Done: missing PLA/PETG/TPU actions now target `runs/physical-<family>-validation`.
2. Done: each missing family action includes a `setup_command` such as `mkdir -p ".../runs/physical-tpu-validation"`.
3. Done: the `record-physical-evidence` command now uses that concrete run folder path.
4. Done: incomplete existing evidence packets still target the existing packet run and do not emit a setup command.
5. Done: the local web action cards render setup commands above the record commands.
6. Boundary: the command still needs real photo paths and real print observations after Zohar physically prints the sample.

## Wave 89 - Physical Validation Starter Packets

Status: complete for pre-print evidence setup. PrintPipe can now create an honest starter packet before a physical validation print.

1. Done: added `printpipe.beta.physical_start.start_physical_validation()`.
2. Done: added `printpipe physical-start --family pla|petg|tpu --runs-dir runs --operator ...`.
3. Done: the command creates `runs/physical-<family>-validation/90_physical/physical_evidence.json` and `.md`.
4. Done: starter packets use `print_status=not_printed`, carry the operator/material/object context, and include notes saying this is not passed evidence.
5. Done: `physical-plan` and the local web action cards now show a `physical-start` command before the later `record-physical-evidence` command.
6. Boundary: starter packets keep `physical-status --strict` failing until a real print is recorded with credible passed evidence and photos.

## Wave 90 - Beta Failure Intake

Status: complete for failure capture plumbing. PrintPipe can now preserve failed beta runs as evidence packets and seed regression manifests.

1. Done: added `printpipe.beta.failures.render_failure_report_markdown()`.
2. Done: added `printpipe.beta.failures.write_failure_report_files()`.
3. Done: added `printpipe record-beta-failure <run-root>` with structured run/material/printer/stage/symptom fields.
4. Done: the command writes `90_beta/failure_report.json` and `.md`, and copies attached artifacts into `90_beta/artifacts/`.
5. Done: `--regression-manifest` appends a `RegressionCase` seeded from the run manifest and the reproduction command.
6. Boundary: this only records failures after they happen; real trusted-user beta runs, physical print failures, and material/orientation/repair rule updates remain open.

## Wave 91 - Regression Manifest Runner

Status: complete for replaying captured beta regression cases. Manifests are now executable, not only authorable.

1. Done: added `printpipe.beta.regression.run_regression_manifest()`.
2. Done: added `printpipe run-regressions <manifest>`.
3. Done: each case records expected outcome, actual outcome, exit code, stdout/stderr, status, and drift message.
4. Done: `expected=failure` passes only when the command still fails.
5. Done: `expected=success` passes only when the command succeeds.
6. Done: `--strict` returns exit code `2` when any case drifts.
7. Boundary: real beta failures and rule updates are still needed before Phase 16 can be marked complete.

## Wave 92 - Regression Readiness Gate

Status: complete for beta-readiness visibility. Regression manifests now feed the same readiness surface as physical, dependency, Bambu, filesystem, and signing gates.

1. Done: added a `beta_regressions` gate to `build_beta_readiness_report()`.
2. Done: missing regression manifests are marked `not_applicable`, so beta readiness stays honest without blocking a first local run.
3. Done: passing regression manifests report the number of captured cases that still match expected outcomes.
4. Done: drifted regression manifests mark readiness `action_required` and point back to `printpipe run-regressions ... --strict`.
5. Done: added `printpipe readiness --regression-manifest <manifest>` so CI, local CLI, or agents can promote captured beta failures into a release gate.
6. Boundary: this does not create trusted-user beta failures or fix material/orientation/repair rules; it only makes captured regressions visible at the readiness layer.

## Wave 93 - Release Regression Gate

Status: complete for final-release gate plumbing. Release status can now include captured beta regression drift, not just release-folder integrity and static readiness.

1. Done: added `regression_manifest_path` to `build_release_status_report()`.
2. Done: release status passes the optional manifest through to `build_beta_readiness_report()`.
3. Done: added `printpipe release-status --regression-manifest <manifest>`.
4. Done: strict release status now returns exit code `2` when the regression manifest drifts.
5. Done: release-status next actions include the regression runner action when beta regression drift blocks the handoff.
6. Boundary: this still does not create real trusted-user failures, physical print evidence, or signed distribution credentials; it only lets final release gating consume those regression manifests when they exist.

## Wave 94 - Web Regression Gate Query

Status: complete for local web/API parity. Browser and agent automation can now ask the local JSON endpoints to include beta regression manifest drift.

1. Done: `/readiness.json?regression_manifest=<path>` passes the manifest path to `build_beta_readiness_report()`.
2. Done: `/release-status.json?regression_manifest=<path>` passes the manifest path to `build_release_status_report()`.
3. Done: blank or omitted query values keep the previous non-blocking default behavior.
4. Done: endpoint tests prove the manifest path reaches the report builders and returns the `beta_regressions` gate.
5. Boundary: the home page still shows the default no-manifest readiness/release panels unless a caller explicitly requests JSON with a manifest path.

## Wave 95 - Web Regression Manifest Configuration

Status: complete for local web UI parity. The browser app can now be launched with a regression manifest so the home panels and service links stay regression-aware by default.

1. Done: added `printpipe serve --regression-manifest <manifest>`.
2. Done: threaded the configured manifest through `PrintPipeWebApp`, `create_app()`, and `serve()`.
3. Done: configured apps pass the manifest into home-page readiness and release-status panels.
4. Done: configured apps add the manifest query to the `Readiness JSON` and `Release status JSON` service links.
5. Done: explicit endpoint query parameters still override the configured manifest for one-off checks.
6. Boundary: this still does not create beta failures, physical print evidence, signed packages, or certificates; it keeps local web visibility aligned with the CLI gates.

## Wave 96 - Beta Action Plan

Status: complete for beta-side action planning. PrintPipe now turns the remaining Phase 16 beta work into a concrete, read-only plan instead of only reporting partial gates.

1. Done: added `printpipe.beta.beta_plan.build_beta_action_plan()`.
2. Done: added `printpipe beta-plan --runs-dir runs` with JSON and human renderers.
3. Done: the plan scans `90_beta/failure_report.json` packets, physical validation status, and an optional regression manifest.
4. Done: missing evidence produces exact next actions for dogfood, physical validation, failure capture, regression replay, trusted-user beta, and material/orientation/repair rule triage.
5. Done: the plan repeats the proof boundary that a generated plan is not trusted-user evidence, physical print proof, or a rule update.
6. Roadmap count remains 132 done / 10 partial because the remaining beta and packaging items still require physical/user/installer evidence.

## Wave 97 - Beta Action Plan in Local Web UI

Status: complete for local web parity. The browser home page and JSON API now expose the same beta action plan as the CLI.

1. Done: added `GET /beta-plan.json`.
2. Done: `/beta-plan.json?regression_manifest=<path>` passes the manifest path through to `build_beta_action_plan()`.
3. Done: `printpipe serve --regression-manifest <manifest>` now configures the home beta-plan panel and JSON service link.
4. Done: the home page renders a `Beta action plan` panel with action cards, commands, and the proof boundary.
5. Done: web tests prove the endpoint, home panel, service link, and configured manifest propagation.
6. Boundary: this is visibility only; it does not create beta failures, physical print evidence, signed packages, or trusted-user feedback.

## Wave 98 - Trusted-User Feedback Packets

Status: complete for trusted-user beta evidence plumbing. PrintPipe can now record successful, partial, failed, or not-run trusted-user feedback separately from failure reports.

1. Done: added `printpipe.beta.feedback` with trusted-user feedback JSON/Markdown packets.
2. Done: added `printpipe record-beta-feedback <run-root>` with tester, outcome, would-print, recommendation, issue, and artifact fields.
3. Done: added `printpipe beta-feedback-status --runs-dir runs --strict`.
4. Done: `build_beta_readiness_report()` now includes a `trusted_user_beta` gate that requires three unique trusted users.
5. Done: `build_beta_action_plan()` now reads trusted feedback status and marks the trusted-user action ready only after that gate passes.
6. Boundary: this records and gates feedback packets; it does not create real trusted-user feedback or close Phase 16 without actual tester evidence.

## Wave 99 - Trusted Feedback Status in Local Web UI

Status: complete for local web parity. The browser app now exposes the same trusted-user beta feedback status as the CLI/readiness layers.

1. Done: added `GET /beta-feedback-status.json`.
2. Done: added a home-page `Trusted-user feedback` panel with overall status, trusted-user count, packet count, tester names, and outcome counts.
3. Done: added a service link to the trusted-user feedback JSON endpoint.
4. Done: web regression tests prove the route, service link, and home panel.
5. Boundary: this is read-only visibility; it does not create tester feedback, physical proof, or final beta completion.

## Wave 100 - Non-Slipper Dogfood Repairs

Status: complete for software dogfood on three non-slipper fixture objects. PrintPipe now has live Bambu CLI slice receipts for the figurine, open-rim cup/vase, and flat bracket paths.

1. Done: dogfooded `simple_figurine_ascii.stl`, `cup_vase_open_frustum.stl`, and `flat_bracket.stl` through `printpipe run --slice` into ignored `runs/dogfood/` folders.
2. Done: fixed the lazy `networkx` dependency exposed by `trimesh.repair.fill_holes()` and added it to the `mesh-repair` extra and environment diagnostics.
3. Done: changed intentional open-rim non-watertight meshes to succeed when `allow_non_watertight=True`, with repair receipts that preserve the boundary-edge warning instead of pretending the mesh is watertight.
4. Done: fixed the flat-bracket orientation regression by applying the selected bed-fit rotation before writing the oriented STL and `.3mf`, so the bundle matches the preview and fits the 256 mm bed.
5. Done: latest successful dogfood runs sliced with 0 warnings: figurine `831s / 1.68g / 170 layers`, cup/vase `1338s / 6.07g / 150 layers`, flat bracket `3408s / 28.18g / 20 layers`.
6. Boundary: this is software/slicer evidence only. It does not replace physical PLA/PETG/TPU print evidence or trusted-user beta packets.

## Wave 101 - Rule Update Evidence Packets

Status: complete for Phase 16 rule-update evidence. Material, orientation, and repair rule changes are now recordable and scannable beta packets.

1. Done: added `printpipe.beta.rule_updates` with JSON/Markdown packets for `material`, `orientation`, and `repair` updates.
2. Done: added `printpipe record-rule-update <run-root>` and `printpipe rule-update-status --runs-dir runs`.
3. Done: beta action plans now include `rule_update_status` and make `update_rules` ready only when material, orientation, and repair updates are verified.
4. Done: readiness now includes a `rule_updates` gate that is `not_applicable` with no packets, `action_required` for incomplete packets, and `ready` when all three rule families are verified.
5. Done: local ignored packets record the Wave 41 PETG/engineering Textured PEI material rule fix, the Wave 100 flat-bracket orientation fix, and the Wave 100 open-rim repair/networkx fix; `rule-update-status --runs-dir runs` reports `passed`.
6. Boundary: rule-update packets are software evidence. Physical PLA/PETG/TPU validation, trusted-user feedback, and signed distribution credentials remain separate gates.

## Wave 102 - Dogfood Failure Regression Coverage

Status: complete for captured software failures. The real Wave 100 dogfood failures are now failure packets with executable regression coverage.

1. Done: added `build_failure_regression_status()` to compare captured `90_beta/failure_report.json` packets against a regression manifest by `source_run_id`.
2. Done: added `printpipe failure-regression-status --runs-dir ... --regression-manifest ...`.
3. Done: readiness now has a `failure_regressions` gate that is not applicable when no failures exist, action-required when failures lack cases, and ready when all captured failures are covered.
4. Done: recorded ignored failure packets for the networkx repair import failure, the open-rim cup/vase repair failure, and the flat-bracket off-bed slice failure.
5. Done: committed `regressions/dogfood_failures.json` with three expected-success cases; `run-regressions regressions/dogfood_failures.json --strict` passes all three.
6. Boundary: this closes software failure capture/regression promotion for current dogfood failures. Real trusted-user beta feedback and physical PLA/PETG/TPU print evidence remain external gates.

## Wave 103 - Physical Evidence UI Hardening

Status: complete for run-detail physical evidence visibility. This does not create physical print evidence.

1. Done: audited the live run-detail contract and confirmed `build_run_detail()` already reads `90_physical/physical_evidence.json`.
2. Done: added regression coverage for no packet, `not_printed`, `partial`, `failed`, `passed`, missing required fields, and artifact links.
3. Done: updated the physical evidence panel to show material, printer, started, and completed fields next to operator, missing evidence, packet links, and artifact links.
4. Done: preserved the boundary that generated flex-coupon artifacts do not count as physical proof and `not_printed`/incomplete packets stay review/incomplete.
5. Boundary: physical PLA/PETG/TPU prints, trusted-user beta feedback, and signed release credentials remain separate gates.

## Wave 104 - Evidence-Based Dogfood Beta Plan

Status: complete for beta-plan dogfood evidence scanning. This does not create physical print evidence or trusted-user feedback.

1. Done: added beta-plan evidence for the canonical software dogfood matrix.
2. Done: `build_beta_action_plan()` now scans run folders for a slipper software run plus three distinct non-slipper live-sliced runs.
3. Done: the dogfood action changes from `action_required` to `ready` when the software matrix is actually present on disk.
4. Done: incomplete dogfood evidence stays action-required and reports the slipper status plus the non-slipper count.
5. Current local result: `printpipe beta-plan --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json` reports dogfood ready and reduces action-required items from 3 to 2.
6. Boundary: physical PLA/PETG/TPU prints and three trusted-user feedback packets remain separate action-required gates.

## Wave 105 - Trusted-User Feedback Action Plan

Status: complete for trusted-user beta planning. This does not create tester feedback evidence.

1. Done: added `build_trusted_user_feedback_plan()` and `render_trusted_user_feedback_plan()`.
2. Done: added `printpipe beta-feedback-plan --runs-dir runs` with JSON and text output.
3. Done: added `/beta-feedback-plan.json` and a home-page `Trusted-user action plan` panel.
4. Done: the plan turns missing trusted-user slots into exact `record-beta-feedback` commands.
5. Boundary: a generated feedback plan is not trusted-user evidence; only completed feedback packets count toward the beta gate.

## Wave 106 - Release Distribution Action Plan

Status: complete for release distribution planning. This does not create signed or notarized release artifacts.

1. Done: added `printpipe.packaging.release_plan.build_release_distribution_plan()`.
2. Done: added `printpipe release-plan --release-dir dist/release --runs-dir runs`.
3. Done: added `/release-plan.json` and a home-page `Release distribution plan` panel.
4. Done: the plan turns macOS Developer ID/notary gaps, Windows signed-installer gaps, and signing prerequisite gaps into exact commands.
5. Current local result: `printpipe release-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json` reports three actions: `macos_distribution`, `windows_distribution`, and `signing`.
6. Boundary: a generated release plan is not signed distribution evidence; final gates still require real Developer ID/notary credentials and a signed Windows installer artifact.

## Wave 107 - Final Action Plan Aggregator

Status: complete for endgame action visibility. This does not create physical, tester, or signed-distribution evidence.

1. Done: added `printpipe.final_plan.build_final_action_plan()` and `render_final_action_plan()`.
2. Done: added `printpipe final-plan --release-dir dist/release --runs-dir runs`.
3. Done: added `/final-plan.json` and a home-page `Final action plan` panel.
4. Done: the final plan preserves the ordered remaining sequence: physical validation, trusted-user beta, then release distribution.
5. Done: the plan sums action counts across `physical-plan`, `beta-feedback-plan`, and `release-plan` while keeping each source proof boundary visible.
6. Boundary: a generated final plan is not evidence; PLA/PETG/TPU passed print packets, three trusted-user feedback packets, Developer ID/notary credentials, and a signed Windows installer artifact remain external gates.

## Wave 108 - Trusted-User Not-Run Gate Hardening

Status: complete for trusted-user beta evidence semantics. This does not create tester feedback evidence.

1. Root cause: `build_trusted_user_feedback_status()` counted every `tester_type=trusted_user` packet as a completed trusted-user slot, including `outcome=not_run`.
2. Done: added regression coverage proving a `not_run` trusted-user packet does not satisfy the trusted-user beta gate.
3. Done: trusted feedback status now reports completed trusted users separately from all trusted-user packets.
4. Done: `not_run_trusted_users` remains visible for auditability, but `unique_trusted_user_count` and `trusted_users` only include completed feedback outcomes.
5. Done: `beta-feedback-plan`, `beta-plan`, `final-plan`, readiness, and local web surfaces inherit the stricter count from the shared status builder.
6. Boundary: failed and partial feedback still count as real feedback because they are completed reviews; only `not_run` is excluded from gate completion.

## Wave 109 - Trusted-User Not-Run Visibility

Status: complete for human-facing beta audit visibility. This does not create tester feedback evidence.

1. Done: added terminal-renderer coverage proving `render_trusted_user_feedback_status()` lists not-run trusted users.
2. Done: added local-web coverage proving the home dashboard shows not-run testers without counting them toward the trusted-user total.
3. Done: the CLI human summary now includes a `Not-run trusted users` section when those packets exist.
4. Done: the local web trusted-user feedback panel now includes a `Not-run testers` card.
5. Done: the card copy states that not-run packets are audit records, not completed beta feedback.
6. Boundary: this is visibility only; completed trusted-user beta still requires three unique trusted users with `passed`, `failed`, or `partial` feedback.

## Wave 110 - Trusted-User Completed-Feedback Wording

Status: complete for trusted-user beta wording consistency. This does not create tester feedback evidence.

1. Done: added readiness regression coverage requiring `completed feedback` wording for the trusted-user gate.
2. Done: added beta-plan regression coverage requiring `completed feedback` wording for missing and ready trusted-user beta actions.
3. Done: updated readiness gate detail from `recorded feedback` to `completed feedback`.
4. Done: updated beta-plan trusted-user action detail from `recorded feedback` to `completed feedback`.
5. Done: updated CLI help and beta documentation to use completed-feedback wording.
6. Boundary: this is wording hardening only; the trusted-user beta gate still requires three unique trusted users with completed `passed`, `failed`, or `partial` feedback packets.

## Wave 111 - Trusted-User Raw Packet Completeness Gate

Status: complete for trusted-user beta scanner hardening. This does not create tester feedback evidence.

1. Root cause: the trusted-feedback status scanner counted raw `trusted_user_feedback.json` packets with blank required fields as completed feedback if the packet said `outcome=passed`.
2. Done: added regression coverage for a hand-written incomplete trusted-user packet with a blank summary.
3. Done: completed trusted-user counts now require a completed outcome (`passed`, `failed`, or `partial`) and no missing required fields.
4. Done: incomplete trusted-user packets stay visible through `incomplete_trusted_user_packet_count` and `incomplete_trusted_user_packets`.
5. Done: the terminal trusted-feedback summary lists incomplete packets and their missing fields.
6. Boundary: generated or hand-edited incomplete packets are audit records only; they do not satisfy trusted-user beta completion.

## Wave 112 - Final Readiness Command Center and Next-Action Contract

Status: complete for endgame action orchestration and home-page visibility. This does not create physical, tester, or signed-distribution evidence.

1. Done: added a home-page `Final readiness / Remaining actions` command-center panel backed by the existing final plan, physical status, and trusted-user status payloads.
2. Done: the panel shows the three real remaining pillars: physical validation, trusted-user beta, and release distribution.
3. Done: the panel flattens remaining endgame actions into one checklist while repeating that generated plans and digital artifacts are not proof.
4. Done: added final-plan regression coverage for top-level `next_action` and `next_command` fields.
5. Done: final-plan JSON now selects the first actionable gate in the existing order and action-specific commands are preferred when present.
6. Current local result: `printpipe final-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json` reports nine actions and a next action of `physical_validation` / `PLA`, with the PLA `physical-start` command as the immediate command.
7. Boundary: this is routing and visibility only; PLA/PETG/TPU physical packets, three trusted-user feedback packets, Developer ID/notary credentials, and signed Windows installer evidence remain external gates.

## Wave 113 - Physical Starter Packet Handoff

Status: partial progress for physical validation. This creates local starter packets, not passed physical evidence.

1. Done: ran `printpipe physical-start --family pla --runs-dir runs --operator Zohar --json`.
2. Done: ran `printpipe physical-start --family petg --runs-dir runs --operator Zohar --json`.
3. Done: ran `printpipe physical-start --family tpu --runs-dir runs --operator Zohar --json`.
4. Done: local ignored packets now exist under `runs/physical-pla-validation/90_physical/`, `runs/physical-petg-validation/90_physical/`, and `runs/physical-tpu-validation/90_physical/`.
5. Done: hardened physical-evidence Markdown so `not_printed` packets list `Physical print not recorded yet` under Open Issues.
6. Current local result: `physical-status --runs-dir runs --json` reports all three families as `recorded_but_not_passed`; `final-plan` still reports nine actions and now points to the PLA `record-physical-evidence` command as the next action.
7. Boundary: the starter packets are local handoff files in ignored `runs/`; they do not satisfy F9 or the physical validation gate until real prints, observations, and photo artifacts are recorded.

## Wave 114 - Physical Validation Coupon Artifacts

Status: partial progress for physical validation. This creates printable local coupon artifacts for the physical handoff, not passed physical evidence.

1. Done: `physical-start` now writes a deterministic `40_geometry/physical_validation_coupon_40x15x3.stl` and JSON sidecar beside each starter evidence packet.
2. Done: the coupon JSON sidecar is material-family-specific: PLA records bed adhesion, first-layer continuity, dimension, and release checks; PETG records adhesion, first-layer continuity, warping, and stringing checks; TPU records adhesion, flex recovery, interlayer bonding, and support/brim removability checks.
3. Done: `physical-start --json` returns `coupon_stl_path` and `coupon_json_path` so the CLI handoff has direct printable artifact paths.
4. Done: `physical-plan --runs-dir runs --json` surfaces existing starter coupon paths for `recorded_but_not_passed` families, so final action planning can point to the actual artifacts on disk.
5. Done: the home-page final-readiness panel renders coupon artifact paths in the remaining physical-validation action rows.
6. Current local result: the ignored PLA, PETG, and TPU starter folders each contain `90_physical/` not-printed packets plus `40_geometry/` coupon STL/JSON artifacts; `physical-status --runs-dir runs --json` still reports all three families as `recorded_but_not_passed`.
7. Boundary: generated coupon files are print inputs only. They do not satisfy F9 or the physical validation gate until the coupons are physically printed, observed, photographed, and recorded as credible evidence packets.

## Wave 115 - Physical Print Handoff Sheets

Status: partial progress for physical validation. This makes the physical starter folders self-contained for a human print day, not passed physical evidence.

1. Done: `physical-start` now writes `90_physical/physical_print_handoff.md` beside each starter evidence packet.
2. Done: the handoff sheet includes the material family, material, object label, run folder, coupon STL path, coupon JSON sidecar path, material-specific validation checks, exact `record-physical-evidence` command, and proof boundary.
3. Done: `physical-start --json` returns `handoff_markdown_path`; non-JSON `physical-start` prints both the coupon STL path and print handoff path.
4. Done: `physical-plan --runs-dir runs` and `--json` surface existing handoff paths for `recorded_but_not_passed` families.
5. Done: the home-page final-readiness panel renders handoff paths beside coupon paths in physical-validation action rows.
6. Current local result: the ignored PLA, PETG, and TPU starter folders each contain `90_physical/physical_print_handoff.md`; `physical-status --runs-dir runs --json` still reports all three families as `recorded_but_not_passed`.
7. Boundary: handoff sheets are instructions and file pointers only. They do not satisfy F9 or the physical validation gate until the coupons are physically printed, observed, photographed, and recorded as credible evidence packets.

## Wave 116 - Trusted-User Beta Review Handoff Sheets

Status: partial progress for trusted-user beta. This creates local tester-review handoff sheets, not completed trusted-user feedback.

1. Done: added `printpipe beta-feedback-start <run-root>` to create a trusted-user beta review handoff without writing `trusted_user_feedback.json`.
2. Done: the handoff sheet includes the run folder, input type, material, printer, report path, bundle path, tester name, review instructions, exact later `record-beta-feedback` command, and completed-feedback proof boundary.
3. Done: `beta-feedback-start --json` returns the handoff path, report path, bundle path, and record command; non-JSON output prints those paths for human use.
4. Done: `beta-feedback-plan --runs-dir runs` now includes a `start_command` for each missing tester slot and surfaces existing handoff paths when present.
5. Done: local ignored handoff sheets now exist for `trusted-user-1`, `trusted-user-2`, and `trusted-user-3` against the slipper proof run.
6. Current local result: `beta-feedback-status --runs-dir runs --json` still reports `insufficient_feedback`, zero completed trusted users, and zero feedback packets.
7. Boundary: handoff sheets are review instructions only. They do not satisfy Phase 16 item 129 until real trusted users complete reviews and their `trusted_user_feedback.json` packets are recorded.

## Wave 117 - Release Distribution Handoff and Evidence Hardening

Status: partial progress for release distribution, physical validation, and trusted-user beta. This creates local release handoff instructions and blocks two fake-proof paths; it does not create signed artifacts, physical prints, or trusted-user feedback.

1. Done: added `printpipe release-start --release-dir <dir> --runs-dir <dir>` to write a release distribution handoff without writing release evidence.
2. Done: the release handoff sheet includes the release dir, runs dir, regression manifest, current release actions, required signing inputs, exact build/check commands, and signed-distribution proof boundary.
3. Done: `release-start --json` returns the handoff path plus `release-status --strict` and `final-plan` check commands; non-JSON output prints the same human handoff paths.
4. Done: `release-plan` now includes `start_command` and existing `handoff_markdown_path` values for release bundle, macOS distribution, Windows distribution, and signing-prerequisite actions; the home-page release distribution cards render those values.
5. Done: physical validation status now rejects a `passed` packet whose photo artifact path does not exist on disk.
6. Done: trusted-user beta status now rejects completed-outcome packets unless the run has an existing report or existing attached artifact file.
7. Current local result: `dist/release_handoffs/release_distribution_handoff.md` exists locally but is ignored; `release-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json` surfaces that handoff for all three release actions.
8. Boundary: release handoffs, existing reports, and attached artifacts are operational evidence only. Items 121 and 122 remain partial until a Developer ID signed/notarized macOS artifact and a signed Windows installer are verified in the release manifest.
