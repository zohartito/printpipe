# Beta Onboarding

Status: local-first beta guide for 3-5 trusted users. This guide is intentionally
plain about the current skeleton pipeline: PrintPipe can create local run
folders and reports, and some internal fixtures exercise bundle-writing code,
but the normal beta CLI path is not print-ready. It has not been physically
validated.

Use this beta only if you are comfortable inspecting files before making a print
decision. If anything here feels unclear, stop and send the artifacts listed
below instead of improvising.

## What This Beta Is Testing

The first beta is about the boring but important spine:

- Can a trusted user set up the local command from a source checkout?
- Does `printpipe doctor` explain the local environment clearly?
- Does a small fixture run create a stable run folder and useful reports?
- Do missing pieces appear honestly instead of pretending the output is ready?
- Can feedback come back with enough artifacts to turn failures into
  regressions?

This is not a full reference-to-print product test yet. Image/video mesh
generation, real repair, automatic orientation, material-specific physical
validation, live Bambu slice verification, and final print judgement are still
limited or incomplete in the regular CLI path.

## Setup

Use a fresh checkout of the repo and run from the repo root.

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
printpipe --version
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
printpipe --version
```

If `printpipe` is not found, reactivate the virtual environment and rerun the
editable install command.

## Run `printpipe doctor`

Before creating a run, capture the local environment check:

```bash
printpipe doctor
printpipe doctor --json
```

The human output is for you. The JSON output is for feedback. It may report
optional missing dependencies or a missing Bambu Studio install. That is useful
signal during this beta, not automatically a failed setup.

## Select The Test Object

Start with the tiny existing-STL fixture:

```text
tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl
```

Why this object:

- It is intentionally small and safe to inspect.
- It avoids private photos and generated meshes.
- It exercises the local run/report path without depending on a large external
  artifact.

After that first run, beta coordinators may assign one non-slipper fixture:

- `tests/fixtures/objects/figurine/simple_figurine_ascii.stl`
- `tests/fixtures/objects/cup_vase/cup_vase_open_frustum.stl`
- `tests/fixtures/objects/flat_bracket/flat_bracket.stl`
- `tests/fixtures/objects/decorative_organic/asymmetric_leaf_shell.stl`

Do not jump to personal objects until the assigned fixture run has been reviewed.

## Run And Inspect

Create a local run:

```bash
printpipe run tests/fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl --runs-dir runs
```

The command prints a run id and report paths. Use the printed run id below:

```bash
printpipe status runs/<run-id>
printpipe open-report runs/<run-id>
```

Open the HTML or Markdown report and read it before sharing feedback. The current
skeleton pipeline should be treated as a report-generation and artifact-discovery
path. It should not be treated as a completed repair, orientation, slicing, or
physical print workflow.

## What Not To Print Yet

Do not start an unattended print from PrintPipe outputs. For this beta, a report
or `.3mf` file from PrintPipe is diagnostic evidence only.

Do not print these from beta outputs yet:

- Do not print footwear for wear.
- Do not print food-contact parts.
- Do not print load-bearing parts.
- Do not print medical or safety-critical parts.
- Do not print parts for children or pets.
- Do not print electrical, heat-exposed, sharp, pressurized, or enclosure parts.

Reason: the current skeleton pipeline is not print-ready and has not been
physically validated. It does not yet prove repair, orientation, support risk,
material settings, slice warnings, or final printer behavior for arbitrary
objects.

Short version: has not been physically validated.

If you choose to inspect something in Bambu Studio, keep it manual: review the
plate, scale, orientation, support preview, layer preview, material profile, and
warnings yourself. Do not upload a PrintPipe-derived file to a printer until a
human reviewer has explicitly cleared that specific artifact.

## Privacy Of Inputs

This beta path is local-first. No cloud upload is required for this beta path,
and the default commands write into local `runs/` folders.

Still, treat inputs and run folders as shareable only after review:

- Do not share private inputs.
- Remove faces, addresses, documents, and location metadata from any screenshot,
  photo, video, mesh, or report you send back.
- Prefer the repo fixtures for the first run because they contain no personal
  data.
- If you test a personal object later, describe the object generically in
  feedback unless the coordinator asks for the actual file.

PrintPipe should not need account credentials for this beta path. Do not paste
API keys, Bambu account tokens, or private cloud links into feedback reports.

## Feedback Artifact List

Send one feedback bundle per run. Include:

- The command you ran and your operating system.
- The `printpipe doctor --json` output.
- `manifest.json`.
- `10_frames/contact_sheet_manifest.json` when present.
- `80_reports/run_report.json`.
- `80_reports/run_report.md`.
- `80_reports/run_report.html`.
- Anything under `60_bundle/`, or a note that `60_bundle/` was missing.
- Any slice log or slice report if you performed a manual Bambu Studio check.
- A screenshot of the report if the report display looked wrong.
- What you expected.
- What happened.
- Whether you opened the report.
- Whether any command failed, hung, printed a warning, or produced a confusing
  path.

It is fine to report "missing" for artifacts that the current skeleton does not
produce yet. The important part is naming the missing artifact and attaching the
run folder evidence that led you there.

## Physical Evidence Packet

When a coordinator explicitly clears a coupon or small-object print, attach a
physical evidence packet instead of only saying that it printed. The helper API
for this is `printpipe.beta.physical`; it records the same fields the beta team
needs before treating a real print as evidence.

Use the CLI to attach the packet to the run folder:

```bash
printpipe record-physical-evidence runs/<run-id> \
  --material "SUNLU TPU 90A" \
  --printer "Bambu Lab P2S" \
  --object-label "flex coupon" \
  --print-type coupon \
  --print-status not_printed
```

The command writes:

- `90_physical/physical_evidence.json`
- `90_physical/physical_evidence.md`

For a real passed, failed, or partial print, attach photo and inspection
artifacts directly to the packet:

```bash
printpipe record-physical-evidence runs/<run-id> \
  --material "SUNLU TPU 90A" \
  --printer "Bambu Lab P2S" \
  --object-label "flex coupon" \
  --print-type coupon \
  --print-status passed \
  --operator "Zohar" \
  --filament-drying "50 C for 6 h" \
  --layer-bonding "no splits after repeated bending" \
  --flex-recovery "returned flat after 20 flexes" \
  --photo /path/to/coupon-photo.jpg \
  --artifact "Layer preview|image|/path/to/layer-preview.png|manual Bambu Studio check"
```

Attached files are copied into `90_physical/artifacts/`, and the run-detail
workbench reads `90_physical/physical_evidence.json` when it exists. If the run
already has `80_reports/run_report.json`, the command also refreshes the static
JSON, Markdown, and HTML reports with a `Physical Evidence` section. A copied
photo is evidence only for what was actually printed; it does not make a planned
print physically validated.

Every physical evidence packet should include:

- Run id and printed object.
- Operator.
- Printer, material, and print status.
- At least one photo artifact for a passed, failed, or partial print.
- Slice status if Bambu Studio or another slicer was checked manually.
- First layer and adhesion notes for PLA and PETG.
- Warping and stringing notes for PETG.
- Filament drying, layer bonding, and flex recovery notes for TPU.
- Dimensions, support-removal notes, or other inspection notes when relevant.

If the print has not happened yet, keep the status as `not_printed`. Do not add
photo, adhesion, or flex claims from memory or from a planned print.

## Feedback Expectations

Good beta feedback is short and concrete:

```text
OS:
PrintPipe command:
Run id:
Test object:
What you expected:
What happened:
Whether you opened the report:
Artifacts attached:
Safety concern, if any:
```

Do not summarize a failure from memory if you still have the run folder. The
run folder is the evidence. If the run exposes a real bug, the next step is to
turn that artifact-backed failure into a regression test.
