# PrintPipe App Roadmap

Status legend: `[ ]` pending, `[x]` done, `[~]` partial, `[!]` blocked.

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
- [~] 19. Move reusable mesh repair into app repo.
- [x] 20. Move Bambu `.3mf` bundling logic into app repo.
- [x] 21. Move settings-delta logic into app repo.
- [x] 22. Move slice-estimate parsing into app repo.
- [x] 23. Archive slipper-specific code as example pipeline.

## Phase 3 - Run Folder and Receipts System

- [x] 24. Create one folder per run.
- [x] 25. Store original input.
- [ ] 26. Store cleaned frames.
- [x] 27. Store generated mesh.
- [~] 28. Store repaired mesh.
- [ ] 29. Store oriented mesh.
- [x] 30. Store profile JSONs.
- [x] 31. Store `.3mf`.
- [ ] 32. Store slice logs.
- [~] 33. Store screenshots/previews.
- [x] 34. Store final run report.

## Phase 4 - Input Processing

- [x] 35. Accept still image.
- [x] 36. Accept GIF.
- [x] 37. Accept video.
- [ ] 38. Extract frames.
- [~] 39. Rank/select best frames.
- [ ] 40. Remove background.
- [ ] 41. Normalize lighting/contrast.
- [~] 42. Save selected references.
- [~] 43. Generate preview contact sheet.

## Phase 5 - Mesh Generation Providers

- [x] 44. Define meshgen provider interface.
- [ ] 45. Add Hunyuan3D provider.
- [x] 46. Add existing-mesh import provider.
- [x] 47. Add placeholder for Replicate/Meshy/Rodin.
- [x] 48. Add retry logic.
- [x] 49. Add provider failure logging.
- [x] 50. Add provider cost/time tracking.

## Phase 6 - Mesh Repair and Validation

- [x] 51. Run mesh topology scan.
- [x] 52. Detect non-manifold edges.
- [x] 53. Detect boundary edges.
- [~] 54. Detect inverted normals.
- [~] 55. Repair with local pipeline.
- [~] 56. Validate watertightness after repair.
- [x] 57. Export repair stats JSON.
- [x] 58. Fail clearly if repair cannot pass.

## Phase 7 - Object Understanding

- [x] 59. Estimate bounding box.
- [ ] 60. Estimate primary axes.
- [~] 61. Detect likely flat base.
- [ ] 62. Detect cavities/openings if possible.
- [x] 63. Generate candidate orientations.
- [x] 64. Score orientations for bed contact.
- [ ] 65. Score orientations for support burden.
- [~] 66. Keep top 3 candidate orientations internally.

## Phase 8 - Scale and Bed Fit

- [ ] 67. Ask or infer intended real-world size.
- [ ] 68. Apply scale.
- [x] 69. Check Bambu bed dimensions.
- [x] 70. Rotate to fit if needed.
- [ ] 71. Decide whether to scale down or fail.
- [x] 72. Drop object to bed.
- [ ] 73. Generate bed-fit visualization.

## Phase 9 - Printer and Filament Engine

- [x] 74. Load Bambu printer profiles.
- [~] 75. Load Bambu/Orca filament defaults.
- [ ] 76. Define material families: PLA, PETG, TPU, ABS/ASA, PC, PA.
- [ ] 77. Create filament override rules.
- [ ] 78. Create process override rules.
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

- [~] 90. Run Bambu CLI slice.
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
- [~] 100. Show input, mesh, repaired mesh, bed fit, and slice summary.
- [x] 101. Show warnings and what changed.
- [~] 102. Show pre-print checklist.

## Phase 13 - Test Objects

- [~] 103. Slipper proof of concept.
- [ ] 104. Simple figurine.
- [ ] 105. Cup/vase object.
- [ ] 106. Flat bracket/wrench-like object.
- [ ] 107. Decorative organic object.
- [~] 108. Existing STL import test.
- [ ] 109. TPU test.
- [ ] 110. PLA test.
- [ ] 111. PETG test.
- [~] 112. Compare all outcomes.

## Phase 14 - Local UI

- [ ] 113. Build local web UI.
- [ ] 114. Drag/drop input.
- [ ] 115. Select Bambu printer.
- [ ] 116. Select filament.
- [ ] 117. Enter target size.
- [ ] 118. Show pipeline progress.
- [ ] 119. Show previews.
- [ ] 120. Download/open `.3mf`.

## Phase 15 - Packaging

- [ ] 121. Package for macOS.
- [ ] 122. Package for Windows.
- [ ] 123. Detect Bambu Studio install path.
- [ ] 124. Detect Bambu user profile folder.
- [ ] 125. Handle missing dependencies.
- [ ] 126. Add updater later, not v1.

## Phase 16 - Beta

- [ ] 127. Dogfood with slipper.
- [ ] 128. Dogfood with 3 non-slipper objects.
- [ ] 129. Give to 3 to 5 trusted users.
- [ ] 130. Collect failed runs.
- [ ] 131. Turn every failure into a regression test.
- [ ] 132. Update material rules.
- [ ] 133. Update orientation rules.
- [ ] 134. Update repair rules.

## Phase 17 - Web/Cloud Later

- [ ] 135. Decide if hosted meshgen is needed.
- [ ] 136. Add backend API only after local works.
- [ ] 137. Add auth.
- [ ] 138. Add storage.
- [ ] 139. Add queue.
- [ ] 140. Add billing.
- [ ] 141. Add hosted GPU workers.
- [ ] 142. Keep local app as power-user version.

## Current Gate

Phase 0 and Phase 1 are complete when this repo is created, tests pass, and the private GitHub remote is pushed.
