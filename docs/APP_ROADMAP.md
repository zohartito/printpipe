# PrintPipe App Roadmap

Status legend: `[ ]` pending, `[x]` done, `[~]` partial, `[!]` blocked.

Original 142-item status after Wave 107: 138 done, 4 partial, 0 pending, 0 blocked.

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

Wave 107 leaves PrintPipe in an honest local-app state for software validation: existing mesh inputs, media/prompt references, repair/orientation, deterministic previews, Bambu-native `.3mf` bundling, static reports, local web workbench views, and optional live Bambu CLI slice receipts are all wired into receipts. The slipper proof now has PrintPipe-generated TPU bundle evidence, a repaired/watertight software path, a generated flex coupon artifact, and run-detail UI that separates digital artifacts from physical proof.

The latest completed wave hardens physical evidence visibility. `printpipe record-physical-evidence` writes `90_physical/physical_evidence.json` and `.md`, copies attached photos/artifacts into `90_physical/artifacts/`, refreshes static reports with a `Physical Evidence` section, and the run-detail workbench now surfaces material, printer, operator, started/completed timestamps, missing-evidence status, packet links, and physical artifact links. Incomplete packets and `not_printed` starter packets stay review/incomplete; generated flex coupons, digital artifacts, and slice receipts do not count as physical proof.

The main local software gates are now explicit and scannable. `printpipe readiness`, `release-status`, and the local web JSON endpoints expose physical validation, trusted-user beta, rule-update, failure-regression, dependency, Bambu, filesystem, signing, macOS distribution, and Windows distribution status. `printpipe final-plan --release-dir dist/release --runs-dir runs` now stitches the remaining physical, trusted-user, and distribution action plans into one ordered endgame checklist while repeating that a generated plan is not evidence. `printpipe beta-plan` now scans run folders for software dogfood evidence and marks the canonical dogfood matrix ready only when it finds a slipper software run plus at least three distinct non-slipper live-sliced runs. `printpipe beta-feedback-plan --runs-dir runs` now turns missing trusted-user beta packets into exact tester-slot actions and `record-beta-feedback` commands, while repeating that a generated plan is not evidence. `printpipe release-plan --release-dir dist/release --runs-dir runs` now turns macOS notarization, Windows signed-installer, and signing-prerequisite gaps into exact build/check commands, while repeating that a generated plan is not signed distribution evidence. Failed dogfood runs have `record-beta-failure` packets plus `regressions/dogfood_failures.json`; `run-regressions regressions/dogfood_failures.json --strict` keeps the captured networkx repair import, open-rim repair allowance, and flat-bracket bed-fit rotation failures covered. Material/orientation/repair rule updates have packet-backed evidence, and the trusted-user feedback packet path is implemented.

The remaining gates are not local code claims: PLA, PETG, and TPU still need credible passed physical evidence packets; three unique trusted users still need feedback packets; Developer ID Application/Installer identities and a notary profile are still needed for final macOS distribution; and Windows still needs a signed installer path with signing tools/certificates. Original items 121 and 122 remain partial until signed/native installer work is complete.

Beta failure intake now has `printpipe record-beta-failure`, which writes `90_beta/failure_report.json` and `.md`, copies attached logs/screenshots/photos into `90_beta/artifacts/`, and can append a regression-manifest case seeded from the failed run and reproduction command. Trusted-user feedback intake now has `printpipe record-beta-feedback`, which writes `90_beta/trusted_user_feedback.json` and `.md` for successful, partial, failed, or not-run beta outcomes. `printpipe beta-feedback-status --runs-dir runs --strict` blocks until three unique trusted users have recorded feedback. `printpipe run-regressions` now replays failure manifests, treating expected failures as passing only while they still fail and expected successes as passing only when they stay green. `printpipe failure-regression-status --runs-dir runs --regression-manifest regressions/dogfood_failures.json --strict` checks that every captured failure packet has a regression case before beta/release claims. `printpipe readiness --regression-manifest <manifest> --strict`, `printpipe release-status --regression-manifest <manifest> --strict`, and `printpipe serve --regression-manifest <manifest>` now promote regression and trusted-user status into beta, release, and local web gates. `printpipe beta-plan --runs-dir runs --regression-manifest <manifest>` now turns the remaining Phase 16 beta work into concrete actions: dogfood matrix, physical validation plan, failure capture command skeleton, regression replay, trusted-user beta, and material/orientation/repair rule-update triage, while repeating that a generated plan is not evidence. `printpipe record-rule-update` now records material, orientation, and repair rule updates as beta packets, and `printpipe rule-update-status --runs-dir runs --strict` verifies all three rule families have packet-backed updates. The current local packets cover the Wave 41 PETG/engineering material bed-type fix and the Wave 100 flat-bracket orientation plus cup/vase repair fixes; the current failure packets cover the Wave 100 networkx, open-rim repair, and flat-bracket slice failures. Real trusted-user packets are still needed to complete Phase 16.

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
- [~] F9. Run one PLA, one PETG, and one TPU physical coupon or small object print and attach evidence; structured evidence packets, starter packets, copied photo/artifact attachments, run-detail UI surfacing, status scanning, physical-plan setup/start/record commands, and browser action-plan visibility are implemented, physical prints are still pending.
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
