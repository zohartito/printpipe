# PrintPipe — Codex Audit Handoff (backend punch-list)

Author: independent senior audit pass (Claude Opus 4.8), 2026-05-28.
Repo: `/Users/zohartito/Desktop/printpipe`  ·  branch `main`  ·  audited at `dd98f67` (+ uncommitted Wave 116 beta-feedback-start).

This is a backend correctness punch-list for Codex. Frontend/UI items are split out at the
bottom for a separate UI agent. Every item below is anchored to a real file:line and a
reproduction that was actually run. Severity: S5 (false completion / fake evidence) · S4
(major broken/misleading workflow) · S3 (reliability/test gap).

---

## Ground rules (read first)
- **Do not fake evidence.** Never create fake physical prints, fake trusted-user packets,
  fake signing/notarization, or fake slice receipts. Gates must only pass on real artifacts.
- **Do not commit or push** unless Zohar explicitly asks.
- **Preserve uncommitted work.** The worktree carries an in-progress Wave 116
  `beta-feedback-start` handoff feature (`feedback.py`, `cli.py`, `test_beta_feedback.py`,
  docs). Make additive/surgical edits; do not revert it.
- After each change: `python -m compileall -q src && .venv/bin/pytest -q` must stay green
  (currently **515 passed, 1 skipped**).

## Baseline truth (verified this pass)
- `printpipe run <stl>` genuinely runs import → repair → orient → bed-fit → `.3mf` →
  validate → report → slice. Real `plate_1.gcode` exists under `runs/dogfood/*/70_slice/`.
  The Bambu CLI SIGSEGV is **resolved** for PrintPipe bundles (Wave 36); roadmap item 90 is
  legitimately done. Do **not** reopen that.
- Physical 0/3, trusted-beta 0/3, signing/notarization absent — all correctly
  `action_required` today.

---

## ALREADY FIXED in this pass (do NOT redo — verify only)
Two S5 hand-edit forgeries were closed and regression-tested:

- **S5-1 physical ghost photo.** `_has_photo` / `missing_required_evidence`
  (`src/printpipe/beta/physical.py`) now take `root=` and require the photo file to exist on
  disk; the gate loader (`src/printpipe/beta/physical_status.py`) passes
  `root=evidence_path.parents[1]`. Regression:
  `tests/test_beta_physical_status.py::test_physical_validation_status_rejects_passed_packet_with_nonexistent_photo`.
- **S5-2 trusted-user bare JSON.** `_packet_summary` now computes `has_supporting_evidence`
  (an existing artifact file OR an existing `80_reports/run_report.*`), and the completion
  predicate in `build_trusted_user_feedback_status` requires it
  (`src/printpipe/beta/feedback.py`). Regression:
  `tests/test_beta_feedback.py::test_trusted_user_feedback_status_rejects_packets_without_supporting_evidence`.

Verify both are still closed:
```bash
# physical: ghost photo must NOT be "passed"
python3 - <<'PY'
import json,subprocess,tempfile;from pathlib import Path
r=Path(tempfile.mkdtemp())/"runs";d=r/"physical-pla-validation"/"90_physical";d.mkdir(parents=True)
(d/"physical_evidence.json").write_text(json.dumps({"run_id":"x","material":"Bambu PLA Basic","printer":"P2S","object_label":"c","print_type":"coupon","print_status":"passed","operator":"Z","first_layer":"ok","adhesion":"ok","artifacts":[{"label":"p","path":"/nonexistent/x.jpg","kind":"photo"}]}))
print(json.loads(subprocess.run([".venv/bin/printpipe","physical-status","--runs-dir",str(r),"--json"],capture_output=True,text=True).stdout)["family_status"]["pla"]["status"])  # -> incomplete
PY
```

---

## REMAINING BACKEND PUNCH-LIST (for Codex)

### S4-1 · Windows release installer is marked signed without any signing
`src/printpipe/packaging/release.py:148-157` (synthesizes `signed=True`), `:369-375`
(`_windows_installer_metadata` hardcodes `signing_kind="authenticode"`), boundary `:321-324`,
verify `:610-613`.
- **Wrong:** any `.exe` passed to `build-release --windows-installer-exe` is recorded as
  Authenticode-signed and `verify-release` returns `ok`. No `signtool` runs.
- **Reproduced first-hand:** `printf 'MZ' > /tmp/fake.exe` → `signed=True,
  signing_kind=authenticode, verify-release: ok`.
- **Fix:** do not synthesize `signed=True`. Default `signed=False`; only set true when a
  real signature is verified (mirror the honest standalone `windows_installer.py` path which
  sets `signed` only after invoking signtool). Optionally add `--assert-windows-signed` that
  fails when verification is unavailable.
- **Test:** `build_release_bundle(windows_installer_exe=<any .exe>)` →
  `artifacts['windows_installer']['signed'] is False`.

### S4-2 · verify-release trusts a hand-edited `notarized:true` manifest (macOS)
gate `src/printpipe/packaging/release_status.py:143-154`; verifier
`src/printpipe/packaging/release.py:455-526` (macos_dmg branch ~`:500-518`); boundary
`release.py:281-305`.
- **Wrong:** copying the real ad-hoc DMG + a manifest claiming
  `notarized:true, signing_kind:developer_id_application` (matching sha256/size) passes
  `verify-release: ok` and flips `macos_distribution` to `ready` "Developer ID signed and
  notarized…". No `codesign`/`stapler` check. (Workflow-verified with real sha256.)
- **Fix:** on `sys.platform == "darwin"`, when an artifact claims `notarized:true`, shell
  `codesign --verify --deep --strict <path>` and `xcrun stapler validate <path>`; fail the
  check on non-zero. Off-darwin, emit an explicit "notarization unverifiable on this
  platform" warning rather than a pass.
- **Test:** build a real ad-hoc DMG, hand-edit manifest to `notarized:true`, assert the
  `artifact_notarization_verify:macos_dmg` check is `failed` (or `skipped_not_macos`).

### S4-3 · image/GIF/video → mesh is entirely unavailable, with no upfront signal
`src/printpipe/meshgen/providers.py:354-366` (Hunyuan3D FAILS on empty command), `:746-748`
(Replicate/Meshy/Rodin are always-FAIL placeholders); `src/printpipe/pipeline/__init__.py:271`
(unconditional `Hunyuan3DProvider()` fallback); dead constant `pipeline/__init__.py:58-61` &
`:1293` (`NON_MESH_MESHGEN_MESSAGE` defined, never used).
- **Verified:** `Hunyuan3DProvider().command == ()` → every non-mesh input FAILS
  `provider_unavailable`. The pipeline reports it honestly at runtime but nothing warns
  upfront that the headline feature can't run here.
- **Fix:** add a meshgen-provider readiness gate that reports `action_required` when no live
  provider is configured (all unconfigured/placeholder). Wire `NON_MESH_MESHGEN_MESSAGE` into
  that gate or delete it.
- **Test:** readiness reports `action_required` for meshgen when no live provider configured.

### S4-4 · Non-STL mesh import (GLB/OBJ/3MF) fails opaquely without optional trimesh
`src/printpipe/meshgen/providers.py:35` (`MESH_SUFFIXES` advertises glb/obj/gltf/3mf);
`pipeline/__init__.py:332` (only FAILED aborts; SKIPPED repair continues), `:852-856`
(`_orientation_source_for_ascii_pipeline` falls back to the original non-STL);
`geometry/artifacts.py:233-234` (raises `ValueError("only ASCII .stl inputs are supported")`).
- **Wrong:** without trimesh (declared optional under `[project.optional-dependencies]
  mesh-repair`), a GLB/OBJ dies at the orientation stage with an error that never mentions the
  missing dependency.
- **Fix:** when repair is SKIPPED because trimesh is unavailable AND the imported mesh is not
  ASCII STL, emit a FAILED `mesh_repair` receipt: "non-STL mesh requires trimesh; install
  printpipe[mesh-repair]" — do not let a non-STL reach the geometry stage.
- **Test:** mock trimesh unavailable, run existing-mesh pipeline on `.obj`; assert failing
  stage is `mesh_repair` and message mentions trimesh/mesh-repair.

### S4-5 · record-physical-evidence with the placeholder photo prints "run root does not exist"
`src/printpipe/cli.py:2168-2173` (catches the artifact `FileNotFoundError` and re-raises as
`FileNotFoundError(run_root)`) → top-level handler `cli.py:1261-1262`. Placeholder path is
emitted by `physical_plan.py:22,32,51,208` (`--photo /path/to/printed-…-coupon-photo.jpg`).
- **Note:** workflow-verified; a quick re-run this pass hit an argparse flag mismatch, so
  **confirm the exact current CLI flags before fixing.**
- **Fix:** in `_record_physical_evidence`, catch the artifact-copy `FileNotFoundError`
  separately and print "photo/artifact file not found: <path>" — the existing run_root check
  (`cli.py` ~`:2128`) already covers a genuinely-missing run folder.
- **Test:** CLI `record-physical-evidence <existing run dir> … --photo /nonexistent.jpg` →
  error message contains "photo"/"artifact", not "run root does not exist".

### S3 · rule_updates gate is NOT_APPLICABLE when captured failures exist but no rule packets
`src/printpipe/beta/readiness.py:175-182`.
- **Wrong:** with real captured dogfood failures present but zero rule-update packets, the
  gate reports `not_applicable` instead of `action_required`, so a release can proceed with
  unaddressed failures.
- **Fix:** when `build_failure_regression_status` finds captured failures in the same
  runs_dir and rule-update status is `missing`, return `action_required`.
- **Test:** one `failure_report.json` + no rule-update packets → rule_updates gate is
  `action_required`.

### S3 · background-removal / lighting-normalization report SUCCEEDED on a no-op copy
`src/printpipe/inputs/processor.py:781-806` and `:843-866`.
- **Wrong:** with no command configured the stages copy files unchanged but return
  `SUCCEEDED`; downstream/report reads this as "preprocessing ran".
- **Fix:** return `StageStatus.SKIPPED` (keep the honest message) when no command ran.
- **Test:** no env command set → background_removal receipt status is `SKIPPED`.

### S3 · corrupt/legacy GLB raises uncaught NotImplementedError through repair
`src/printpipe/mesh/repair.py:133-166` (catches only `MeshRepairUnavailableError`/
`MeshRepairError`).
- **Wrong:** trimesh raises `NotImplementedError` for non-GLTF2 GLB headers → raw traceback
  instead of a FAILED stage receipt.
- **Fix:** also catch `(NotImplementedError, ValueError, TypeError)` and return a FAILED
  receipt explaining the mesh could not be loaded.
- **Test:** a GLB with a non-GLTF2 header → `repair_mesh_file_to_receipt` returns FAILED (no
  raise).

---

## NOT for Codex — route to the UI agent (Cursor)
These are frontend honesty issues, listed so they aren't lost:
- **S4** Home run-cards show "succeeded" + a direct `.3mf` download with no "Review before
  print" verdict (`web/server.py:1322-1358` vs `runs/detail.py:66`).
- **S3** Run-detail view tabs (Bed Fit/Slice/…) are static `<span>`s — clicking does nothing
  (`web/run_detail.py:239`).
- **S2** Trusted-feedback "Outcomes" card hardcodes `status=recorded` at all-zero
  (`web/server.py:1168`).
- **S1** Static HTML report renders artifact links with no existence check
  (`reports/html.py:895`).
- **S2** `physical-start` human output omits the coupon STL path (`cli.py:1706`).

## Suggested order
S4-1 → S4-2 (both are false signing claims) → S4-3 → S4-4 → S4-5 → the three S3s.

## Verification after each fix
```bash
cd /Users/zohartito/Desktop/printpipe
python -m compileall -q src
.venv/bin/pytest -q          # keep green (515 passed, 1 skipped)
git diff --check
```
