# PrintPipe App Roadmap

Status legend: `[ ]` pending, `[x]` done, `[~]` partial, `[!]` blocked.

Original 142-item status after Wave 44: 132 done, 10 partial, 0 pending, 0 blocked.

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
- [~] 128. Dogfood with 3 non-slipper objects.
- [~] 129. Give to 3 to 5 trusted users.
- [~] 130. Collect failed runs.
- [~] 131. Turn every failure into a regression test.
- [~] 132. Update material rules.
- [~] 133. Update orientation rules.
- [~] 134. Update repair rules.

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

Wave 44 leaves the product in an honest local-app state: existing mesh inputs run end-to-end into repaired/oriented geometry, deterministic previews, Bambu `.3mf`, reports, and optional slice-gate receipts. Image/GIF/video inputs now prepare references, rank frames with a representative spread strategy, optionally run configured background-removal and lighting-normalization commands, call the configured Hunyuan3D local adapter, and then continue through the same repair/orient/bundle/report spine. If `PRINTPIPE_HUNYUAN3D_COMMAND` is unset, media runs fail at `meshgen` with a provider-configuration receipt instead of silently pretending to generate geometry. Mesh validation now detects boundary edges, non-manifold edges, inconsistent winding, and globally inverted closed-shell normals when vertex coordinates are available. The wide-upper slipper mesh has now run through PrintPipe itself with SUNLU TPU 90A material intent, TPU profile IDs/settings in the `.3mf`, 0 warnings, a watertight repair receipt, bed-fit receipt, bundle validation, and a generated flex-coupon artifact. PLA/PLA+, PETG, TPU, ABS, ASA, PC, PA, and PA-CF software material tests now generate Bambu-native bundles with full resolved machine/process/filament settings and have live Bambu CLI slice receipts on macOS; PETG and engineering/high-temperature materials explicitly set `curr_bed_type=Textured PEI Plate` so Bambu does not reject them as Cool Plate jobs. Physical print evidence now has a structured beta packet for real coupon/object results plus `printpipe record-physical-evidence`, which writes `90_physical/physical_evidence.json` and `.md`, copies attached photos/artifacts into `90_physical/artifacts/`, and surfaces the packet in the run-detail UI; the actual PLA/PETG/TPU physical prints are still not complete. The macOS and Windows package work now includes a portable `printpipe.pyz` zipapp artifact that runs `--version` and package-smoke outside editable-install console scripts; the same zipapp artifact has passed package-smoke on Windows over SSH. This is still not a signed/notarized `.app` or signed Windows installer, so original items 121 and 122 remain partial. The Bambu CLI slice gate is now verified for PrintPipe-generated Bambu-native `.3mf` bundles on this host: PLA, PETG, TPU, ABS, ASA, PC, PA, and PA-CF runs returned code 0 with G-code and zero warnings/errors, and raw direct-STL CLI crashes are documented as outside the supported slice path. The run-detail UI and CLI both expose local open-folder affordances for bundle/report folders, and run-detail `.3mf` artifact tiles now render a browser download affordance for the Bambu bundle itself. `printpipe doctor` now reports workspace and configured artifact readability, web run status marks unreadable external artifacts without crashing, and troubleshooting docs include the macOS Desktop/TCC recovery path.

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
- [~] F9. Run one PLA, one PETG, and one TPU physical coupon or small object print and attach evidence; structured evidence packets, copied photo/artifact attachments, and run-detail UI surfacing are implemented, physical prints are still pending.
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
