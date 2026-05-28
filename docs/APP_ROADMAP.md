# PrintPipe App Roadmap

Status legend: `[ ]` pending, `[x]` done, `[~]` partial, `[!]` blocked.

Original 142-item status after Wave 142: 138 done, 4 partial, 0 pending, 0 blocked.

Latest status: Wave 142 aligned the beta docs and local physical handoff sheets with Wave 141's placeholder-outcome rule. Generated `record-physical-evidence` commands now preserve the concrete run folder, printer, material, object, and observation prompts, but require the operator to replace `--print-status "<passed|failed|partial>"` after the coupon is actually printed. The tracked beta docs and current local PLA/PETG/TPU handoff sheets no longer present a copy-pasteable passing physical record before evidence exists.

## Goal

Complete a local-first program that turns an image, GIF, video, or existing mesh plus Bambu printer and filament intent into a repaired, oriented, profile-tuned, slice-verified Bambu `.3mf` with receipts.

## Phase 0 - Product Ground Rules

- [x] 1. Define v1 as local-first, not public web.
- [x] 2. Define Bambu-only printer support for launch.
- [x] 3. Define supported inputs: image, GIF, video, existing mesh.
- [x] 4. Define supported outputs: `.stl`, `.glb`, `.3mf`, slice report, settings report.
- [x] 5. Define one-shot acceptance: no manual Rhino/Blender repair required.
- [x] 6. Define success as slice-verified, not just mesh-generated.

## Phase 1 - Repo and Project Setup

- [x] 7. Create new private GitHub repo for the app.
- [x] 8. Choose temporary codename: `printpipe`.
- [x] 9. Pick tech stack: Python pipeline first.
- [x] 10. Add project structure.
- [x] 11. Add dependency manager/project metadata.
- [x] 12. Add basic test runner.
- [x] 13. Add README with v1 scope.
- [x] 14. Add architecture doc.
- [x] 15. Add run artifact folder convention.

## Phase 2 - Extract the Slipper Pipeline

- [x] 16. Inventory current slipper scripts.
- [x] 17. Identify reusable parts.
- [x] 18. Identify slipper-specific hardcoded assumptions.
- [x] 19. Move reusable mesh repair into app repo.
- [x] 20. Move Bambu `.3mf` bundling logic into app repo.
- [x] 21. Move settings-delta logic into app repo.
- [x] 22. Move slice-estimate parsing into app repo.
- [x] 23. Archive slipper-specific code as example pipeline.

## Phase 3 - Run Folder and Receipts System

- [x] 24. Create one folder per run.
- [x] 25. Store original input.
- [x] 26. Store cleaned frames.
- [x] 27. Store generated mesh.
- [x] 28. Store repaired mesh.
- [x] 29. Store oriented mesh.
- [x] 30. Store profile JSONs.
- [x] 31. Store `.3mf`.
- [x] 32. Store slice logs.
- [x] 33. Store screenshots/previews.
- [x] 34. Store final run report.

## Phase 4 - Input Processing

- [x] 35. Accept still image.
- [x] 36. Accept GIF.
- [x] 37. Accept video.
- [x] 38. Extract frames.
- [x] 39. Rank/select best frames.
- [x] 40. Remove background.
- [x] 41. Normalize lighting/contrast.
- [x] 42. Save selected references.
- [x] 43. Generate preview contact sheet.

## Phase 5 - Mesh Generation Providers

- [x] 44. Define meshgen provider interface.
- [x] 45. Add Hunyuan3D provider.
- [x] 46. Add existing-mesh import provider.
- [x] 47. Add placeholder for Replicate/Meshy/Rodin.
- [x] 48. Add retry logic.
- [x] 49. Add provider failure logging.
- [x] 50. Add provider cost/time tracking.

## Phase 6 - Mesh Repair and Validation

- [x] 51. Run mesh topology scan.
- [x] 52. Detect non-manifold edges.
- [x] 53. Detect boundary edges.
- [x] 54. Detect inverted normals.
- [x] 55. Repair with local pipeline.
- [x] 56. Validate watertightness after repair.
- [x] 57. Export repair stats JSON.
- [x] 58. Fail clearly if repair cannot pass.

## Phase 7 - Object Understanding

- [x] 59. Estimate bounding box.
- [x] 60. Estimate primary axes.
- [x] 61. Detect likely flat base.
- [x] 62. Detect cavities/openings if possible.
- [x] 63. Generate candidate orientations.
- [x] 64. Score orientations for bed contact.
- [x] 65. Score orientations for support burden.
- [x] 66. Keep top 3 candidate orientations internally.

## Phase 8 - Scale and Bed Fit

- [x] 67. Ask or infer intended real-world size.
- [x] 68. Apply scale.
- [x] 69. Check Bambu bed dimensions.
- [x] 70. Rotate to fit if needed.
- [x] 71. Decide whether to scale down or fail.
- [x] 72. Drop object to bed.
- [x] 73. Generate bed-fit visualization.

## Phase 9 - Printer and Filament Engine

- [x] 74. Load Bambu printer profiles.
- [x] 75. Load Bambu/Orca filament defaults.
- [x] 76. Define material families: PLA, PETG, TPU, ABS/ASA, PC, PA.
- [x] 77. Create filament override rules.
- [x] 78. Create process override rules.
- [x] 79. Validate enum values against Bambu schema/source.
- [x] 80. Generate settings delta report.
- [x] 81. Attach reason to every changed setting.

## Phase 10 - 3MF Bundling

- [x] 82. Build Bambu-native `.3mf`.
- [x] 83. Include model.
- [x] 84. Include printer profile.
- [x] 85. Include filament profile.
- [x] 86. Include process profile.
- [x] 87. Include correct Bambu metadata signature.
- [x] 88. Include GUI-safe bed transform.
- [x] 89. Validate `.3mf` contents before delivery.

## Phase 11 - Slice Gate

- [x] 90. Run Bambu CLI slice.
- [x] 91. Parse warnings/errors.
- [x] 92. Extract time, mass, layers, cost.
- [x] 93. Fail or retry if non-manifold, off-bed, enum replacement, or floating cantilever.
- [x] 94. Save gcode/slice logs.
- [x] 95. Generate final slice report.

## Phase 12 - Verification UX

- [x] 96. Create local command: `printpipe run input.gif`.
- [x] 97. Create `printpipe status`.
- [x] 98. Create `printpipe open-report`.
- [x] 99. Create HTML run report.
- [x] 100. Show input, mesh, repaired mesh, bed fit, and slice summary.
- [x] 101. Show warnings and what changed.
- [x] 102. Show pre-print checklist.

## Phase 13 - Test Objects

- [x] 103. Slipper proof of concept.
- [x] 104. Simple figurine.
- [x] 105. Cup/vase object.
- [x] 106. Flat bracket/wrench-like object.
- [x] 107. Decorative organic object.
- [x] 108. Existing STL import test.
- [x] 109. TPU test.
- [x] 110. PLA test.
- [x] 111. PETG test.
- [x] 112. Compare all outcomes.

## Phase 14 - Local UI

- [x] 113. Build local web UI.
- [x] 114. Drag/drop input.
- [x] 115. Select Bambu printer.
- [x] 116. Select filament.
- [x] 117. Enter target size.
- [x] 118. Show pipeline progress.
- [x] 119. Show previews.
- [x] 120. Download/open `.3mf`.

## Phase 15 - Packaging

- [~] 121. Package for macOS.
- [~] 122. Package for Windows.
- [x] 123. Detect Bambu Studio install path.
- [x] 124. Detect Bambu user profile folder.
- [x] 125. Handle missing dependencies.
- [x] 126. Add updater later, not v1.

## Phase 16 - Beta

- [~] 127. Dogfood with slipper.
- [x] 128. Dogfood with 3 non-slipper objects.
- [~] 129. Give to 3 to 5 trusted users.
- [x] 130. Collect failed runs.
- [x] 131. Turn every failure into a regression test.
- [x] 132. Update material rules.
- [x] 133. Update orientation rules.
- [x] 134. Update repair rules.

## Phase 17 - Web/Cloud Later

- [x] 135. Decide if hosted meshgen is needed.
- [x] 136. Add backend API only after local works.
- [x] 137. Add auth.
- [x] 138. Add storage.
- [x] 139. Add queue.
- [x] 140. Add billing.
- [x] 141. Add hosted GPU workers.
- [x] 142. Keep local app as power-user version.

## Current Gate

Wave 140 leaves PrintPipe in an honest local-app state for software validation: existing mesh inputs, media/prompt references, repair/orientation, deterministic previews, Bambu-native `.3mf` bundling, static reports, local web workbench views, optional live Bambu CLI slice receipts, physical print handoffs, trusted-user beta handoffs, release distribution handoffs, and default regression-aware CLI/web readiness/planning are all wired into receipts. The slipper proof now has PrintPipe-generated TPU bundle evidence, a repaired/watertight software path, a generated flex coupon artifact, and run-detail/final-readiness UI that separates digital artifacts from physical, beta, or signed-distribution proof.

The latest completed wave hardened trusted-user beta record commands against fake-positive evidence. Generated `record-beta-feedback` templates no longer default to `--outcome passed`, `--would-print no`, or `--recommendation needs_review`; they keep concrete run/tester/material/report context, but require the reviewer outcome fields to be filled in after the review. The beta gate remains open until real trusted users return completed packets.

Wave 139 made trusted-user beta handoff rows operational instead of placeholder-heavy. When a `trusted_user_feedback_handoff_*.md` file exists, `beta-feedback-plan` and `final-plan` now point the immediate action at the real run folder and produce a concrete `record-beta-feedback` command with the actual run root, tester slot, input type, material, printer, and report artifact path. The beta gate remains open until real trusted users return completed packets.

Wave 138 made the remaining endgame planning commands use the same standard `regressions/dogfood_failures.json` manifest when that file exists. `beta-plan`, `release-status`, `release-plan`, `release-start`, `final-plan`, and `final-next` now default to the dogfood regression manifest unless an explicit path is provided. That keeps terminal planning, release handoffs, and final next-action checks aligned with readiness and the local web app.

Wave 137 made default local web launches use the same standard `regressions/dogfood_failures.json` manifest when that file exists. `printpipe serve --runs-dir runs` now feeds the local home page, readiness JSON, release status, beta plan, and final readiness surfaces the regression-aware gate state without requiring a remembered `--regression-manifest` flag. Explicit manifest paths still override the default.

Wave 136 made the default terminal readiness command use the standard `regressions/dogfood_failures.json` manifest when that file exists. `printpipe readiness --runs-dir runs --strict` now reports the same regression-aware truth as the configured local web server: physical validation, trusted-user beta, and release signing remain action-required, while failure regression coverage and beta regression replay are ready. Repos without that standard manifest still keep the beta regression gate optional/not-applicable unless a manifest path is provided.

Wave 135 made final-readiness run artifact paths actionable in the local web UI. Paths under `runs/<run-id>/...` now link to the existing safe `/runs/<run-id>/artifacts/...` route from the top next-action callout and checklist rows, while non-run local paths remain plain text. This still does not create evidence; it just reduces friction when opening reports, bundles, handoffs, and receipts.

Wave 134 made terminal `final-plan` action rows self-contained, not just the top next action. Each physical, trusted-user, and release section row can now show details, required inputs, start/setup/build commands, follow-up checks, record-after-print/review commands, and supporting artifact/handoff paths. This still does not close any external gate; it just makes the complete terminal checklist operational.

Wave 133 made `final-next` truthful when release distribution becomes the active top action. Release next-action payloads, terminal output, and the web top callout can now carry required signing/tool inputs, the immediate `release-start` handoff command, the actual build/check command to run after prerequisites, follow-up verification, and release handoff paths. This still does not count as signed distribution evidence; Developer ID/notary credentials and a signed Windows installer remain external gates.

Wave 132 made release distribution rows self-contained for final handoff. The web final-readiness checklist can now show required signing/tool inputs, the existing release handoff Markdown, the immediate `release-start` handoff command, the actual build/check command to run after prerequisites, and the follow-up verification command. This still does not count as signed distribution evidence; Developer ID/notary credentials and a signed Windows installer remain external gates.

Wave 131 made trusted-user beta rows self-contained for review handoff. `beta-feedback-plan` now preserves the existing review handoff Markdown plus the run report and Bambu `.3mf` bundle paths for each trusted-user slot, and the web final-readiness checklist renders those files with a contextual `Record after review` command. This still does not count as tester evidence; the beta gate remains open until three unique trusted users return completed packets.

Wave 130 made the web final-readiness rows self-contained for physical validation. Each material row can now show the coupon STL, Bambu `.3mf`, bundle-validation JSON, slice receipt, handoff Markdown, immediate handoff command, and post-print record command.

Wave 129 aligned the web final-readiness checklist rows with the top next-action panel. Every already-started physical validation row can now show the immediate handoff command and the post-print `record-physical-evidence` command, while starter/setup actions still hide premature record commands.

Wave 128 made the final next-action handoff more complete without changing the immediate command. `final-next` and the web final-readiness panel still point first at `printpipe open-folder ... --target run`, but now also carry and render the post-print `record-physical-evidence` command as `record after print`.

Wave 127 made the physical print handoff more useful on print day. `physical-slice` now carries time, filament, layer-count, and cost fields from the slice receipt into its JSON payload and renders a compact estimate line inside `90_physical/physical_print_handoff.md`.

Wave 126 tightened physical print handoff truth. `physical-slice` now refreshes only the `## Slice Receipt` section inside `90_physical/physical_print_handoff.md`, so the handoff file Zohar opens before printing agrees with the available `70_slice/slice_result.json` receipt while leaving `90_physical/physical_evidence.json` untouched.

Wave 125 added `physical-slice`, a non-destructive way to slice an existing validation coupon bundle without recreating the starter packet or rewriting its not-yet-printed physical evidence packet. Physical plans now show a `slice:` command whenever a coupon bundle exists but no slice receipt exists yet.

Wave 124 added an explicit `physical-start --slice` path for validation coupons. Starter packets remain usable without Bambu Studio, but when slicing is requested they now write a `70_slice/slice_result.json` receipt through the existing Bambu CLI slice wrapper and surface that path through physical plans and `final-next`.

Wave 123 made `physical-start` produce Bambu-ready coupon `.3mf` bundles in addition to STL/JSON sidecars and physical handoffs. The coupon bundle uses the same material-aware Bambu profile resolution path as normal runs, writes a bundle-validation JSON receipt, and is surfaced through physical plans as `bundle_path`.

Wave 122 tightened physical next-action honesty. Started but not printed physical-validation starter packets now make `final-next` point at `printpipe open-folder "<run>" --target run` so the user sees the coupon STL and physical handoff first. The post-print `record-physical-evidence ... --print-status "<passed|failed|partial>" ... --photo ...` command remains present as `record_command`, but is no longer treated as the immediate command before a real print exists and no longer preselects a passing result.

Wave 121 added `/final-next.json` to the local web app and moved the focused next-action JSON into a shared helper used by both the CLI and web endpoint. Agents, Cursor, Claude, and UI clients can now read the immediate final action without parsing full section data.

Wave 120 added `printpipe final-next`, a narrow command that renders only the immediate endgame action plus its supporting files and proof boundary. It uses the same `final-plan` data, so `final-next --json` returns `overall_status`, `action_count`, `proof_boundary`, `next_action`, and `next_command` without requiring agents or users to parse the full section checklist.

Wave 119 aligned the terminal `final-plan` renderer with the JSON contract and home-page callout. The human CLI output now prints next-action supporting files (`artifact`, `sidecar`, `handoff`, `report`, `bundle`) directly under the immediate command, so the current PLA physical-validation action includes the coupon STL, coupon JSON, and print handoff in all three surfaces: terminal, JSON, and web.

Wave 118 made the top-level next action carry its required evidence files. `final-plan` now preserves action-specific artifact and handoff paths on `next_action`, including physical coupon STL/JSON paths, print handoff Markdown, trusted-user report/bundle paths, and release handoff paths when those are the active next action. The home-page `Final readiness / Remaining actions` callout now renders those next-action files beside the immediate command, so the first action is no longer just a shell command with hidden supporting files.

Wave 117 made the release distribution gate self-contained for handoff without fabricating signed artifacts. `release-start` now writes `dist/release_handoffs/release_distribution_handoff.md`, including the release dir, runs dir, regression manifest, current release actions, required signing inputs, exact build/check commands, and signed-distribution proof boundary. `release-plan` and the home-page final-readiness surfaces now show the `release-start` command and existing handoff path for macOS, Windows, and signing-prerequisite actions. Physical and trusted-user gates were also hardened: a passed physical packet only counts when its referenced photo exists on disk, and a completed trusted-user packet only counts when the run has an existing report or existing attached artifact. `release-status` still reports action required because Developer ID/notary credentials and a signed Windows installer are not present.

Wave 116 made the trusted-user beta gate self-contained for tester handoff without fabricating feedback. `beta-feedback-start` now writes `90_beta/trusted_user_feedback_handoff_<tester>.md` for a chosen run and tester, including report and bundle paths, review instructions, the exact later `record-beta-feedback` command, and the completed-feedback proof boundary. Local ignored handoff sheets now exist for three trusted-user slots against the slipper proof run, and `beta-feedback-plan`/final-readiness surfaces those handoff paths. `beta-feedback-status` still reports zero completed trusted users, so Phase 16 item 129 remains partial until real testers return completed feedback packets.

The main local software gates are now explicit and scannable. `printpipe readiness`, `release-status`, and the local web JSON endpoints expose physical validation, trusted-user beta, rule-update, failure-regression, dependency, Bambu, filesystem, signing, macOS distribution, and Windows distribution status. `printpipe final-plan --release-dir dist/release --runs-dir runs` stitches the remaining physical, trusted-user, and distribution action plans into one ordered endgame checklist while repeating that a generated plan is not evidence. `printpipe beta-plan` now scans run folders for software dogfood evidence and marks the canonical dogfood matrix ready only when it finds a slipper software run plus at least three distinct non-slipper live-sliced runs. `printpipe beta-feedback-plan --runs-dir runs` now turns missing trusted-user beta packets into exact tester-slot actions and `record-beta-feedback` commands, while repeating that a generated plan is not evidence. `printpipe release-plan --release-dir dist/release --runs-dir runs` now turns macOS notarization, Windows signed-installer, and signing-prerequisite gaps into exact build/check commands, while repeating that a generated plan is not signed distribution evidence. Failed dogfood runs have `record-beta-failure` packets plus `regressions/dogfood_failures.json`; `run-regressions regressions/dogfood_failures.json --strict` keeps the captured networkx repair import, open-rim repair allowance, and flat-bracket bed-fit rotation failures covered. Material/orientation/repair rule updates have packet-backed evidence, and the trusted-user feedback packet path is implemented.

The remaining gates are not local code claims: PLA, PETG, and TPU still need credible passed physical evidence packets; three unique trusted users still need feedback packets; Developer ID Application/Installer identities and a notary profile are still needed for final macOS distribution; and Windows still needs a signed installer path with signing tools/certificates. Original items 121 and 122 remain partial until signed/native installer work is complete.

Beta failure intake now has `printpipe record-beta-failure`, which writes `90_beta/failure_report.json` and `.md`, copies attached logs/screenshots/photos into `90_beta/artifacts/`, and can append a regression-manifest case seeded from the failed run and reproduction command. Trusted-user feedback intake now has `printpipe record-beta-feedback`, which writes `90_beta/trusted_user_feedback.json` and `.md` for successful, partial, failed, or not-run beta outcomes. `printpipe beta-feedback-status --runs-dir runs --strict` blocks until three unique trusted users have completed feedback; `not_run` and incomplete raw packets remain visible in JSON and terminal summaries but do not satisfy the gate. Readiness and beta-plan copy now uses "completed feedback" instead of "recorded feedback" so a recorded `not_run` packet cannot be misread as gate completion. `printpipe run-regressions` now replays failure manifests, treating expected failures as passing only while they still fail and expected successes as passing only when they stay green. `printpipe failure-regression-status --runs-dir runs --regression-manifest regressions/dogfood_failures.json --strict` checks that every captured failure packet has a regression case before beta/release claims. `printpipe readiness --regression-manifest <manifest> --strict`, `printpipe release-status --regression-manifest <manifest> --strict`, and `printpipe serve --regression-manifest <manifest>` now promote regression and trusted-user status into beta, release, and local web gates. `printpipe beta-plan --runs-dir runs --regression-manifest <manifest>` now turns the remaining Phase 16 beta work into concrete actions: dogfood matrix, physical validation plan, failure capture command skeleton, regression replay, trusted-user beta, and material/orientation/repair rule-update triage, while repeating that a generated plan is not evidence. `printpipe record-rule-update` now records material, orientation, and repair rule updates as beta packets, and `printpipe rule-update-status --runs-dir runs --strict` verifies all three rule families have packet-backed updates. The current local packets cover the Wave 41 PETG/engineering material bed-type fix and the Wave 100 flat-bracket orientation plus cup/vase repair fixes; the current failure packets cover the Wave 100 networkx, open-rim repair, and flat-bracket slice failures. Real trusted-user packets are still needed to complete Phase 16.

## Post-Wave 13 Findings Backlog

These items are not part of the original 142 count. They come from Wave 13 verification and should be treated as the next execution backlog.

- [x] F1. Fix or document macOS Desktop/TCC permission recovery for the primary checkout.
- [x] F2. Add a `printpipe doctor` check that warns when the current workspace or external artifact paths are unreadable.
- [x] F3. Add a run option that deliberately invokes live Bambu CLI slicing against the generated `.3mf` and records the real receipt.
- [x] F4. Wire image/GIF/video runs through Hunyuan3D meshgen, repair, orientation, bundle, and report.
- [x] F5. Add real mesh preview screenshots or deterministic rendered previews, not only SVG/contact-sheet previews.
- [x] F6. Add one-click "open bundle/report folder" affordance for local macOS/Windows flows.
- [x] F7. Create a flex-coupon generator and include it as the first TPU validation artifact.
- [x] F8. Run the slipper proof through PrintPipe, not the old external slipper repo.
- [~] F9. Run one PLA, one PETG, and one TPU physical coupon or small object print and attach evidence; structured evidence packets, material-specific starter coupon STL/JSON artifacts, physical print handoff sheets, copied photo/artifact attachments, run-detail UI surfacing, status scanning, physical-plan setup/start/record commands, and browser action-plan visibility are implemented, physical prints are still pending.
- [x] F10. Build a clean macOS app/package smoke path.
- [x] F11. Build a clean Windows package smoke path.
- [x] F12. Add a regression for unreadable external artifact paths so permission problems skip or report clearly instead of crashing.
- [x] F13. Isolate Bambu Studio 2.6.00.51 CLI `--slice` SIGSEGV on macOS 26.5; PrintPipe now slices Bambu-native `.3mf` bundles with fully resolved project settings, while raw direct-STL CLI crashes remain documented as outside the supported path.
- [x] F14. Add run-detail workbench route with print verdict, preview/workbench area, artifact links, and edit controls.
- [x] F15. Add non-destructive edit recipes and child edit runs.
- [x] F16. Rebuild edit runs deterministically from saved recipes, with scale-only geometry and explicit semantic warnings.
- [x] F17. Add a CLI `printpipe rebuild-edit` command.
- [x] F18. Make image/GIF/video runs write failed `meshgen` receipts instead of silent prep-only success.
- [x] F19. Surface first classified Bambu slice error in the receipt/report message.
