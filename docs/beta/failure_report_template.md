# PrintPipe Beta Failure Report

Use this report when a beta run fails in software, slicing, printer handoff, or physical printing. Keep paths local when the artifact is in a run folder, and include links only when the artifact has already been shared.

## Run Context

- Run ID:
- Input type:
- Material:
- Printer:
- Reporter:
- Date captured:

## Failure Details

- Failed stage:
- Error message:
- Expected result:
- Actual result:

## Symptoms

- Describe visible symptoms, terminal output, slicer warnings, or printer behavior:

## Artifacts

- `runs/<run-id>/manifest.json`:
- `runs/<run-id>/80_reports/run_report.json`:
- Additional logs, screenshots, photos, or generated files:

## Reproduction

```bash
printpipe run <input-path> --material <material>
```

- Environment notes:
- Any manual steps before failure:

## Physical Print Status

- Status: not_printed / sent_to_printer / failed_on_printer / partially_printed / completed_with_defects
- Printer job ID:
- First-layer observations:
- Physical defect notes:
- Photo/video artifacts:

## Triage Notes

- Suspected cause:
- Owner:
- Next action:
