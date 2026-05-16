# Wave 3 Integration Summary

Status: complete

Wave 3 connected the core skeleton into a verification spine. PrintPipe can now create a run, prepare dependency-light input artifacts, write JSON/Markdown/HTML reports, classify slicer output, score basic bed-fit candidates, export settings deltas, and carry small regression fixtures.

## Outputs

- `src/printpipe/bambu/slicer.py`: slice result model, warning/error classifier, estimate parser, subprocess wrapper that writes logs, and hard gate.
- `src/printpipe/bambu/profiles/report.py`: settings delta JSON/Markdown exports and summary helpers.
- `src/printpipe/geometry/`: dependency-light bounds, Z-rotation candidates, bed-fit scoring, XY-centering, Z-drop, and flat-base diagnostic.
- `src/printpipe/reports/html.py`: dependency-free HTML report renderer and writer.
- `src/printpipe/cli.py`: `run`, `status`, and `open-report` commands.
- `tests/fixtures/`: minimal topology and slicer-log fixtures.
- `docs/research/wave3_fixture_strategy.md`: policy for turning failed runs into regression fixtures.

## Verification

Full suite:

```text
.venv/bin/python -m pytest
68 passed
```

## Honest Limitations

- `run_slice_command` can invoke a command and log output, but no real Bambu Studio CLI integration test has run yet.
- Orientation scoring handles simple Z rotations and bed fit; it does not understand semantic upright orientation, cavities, or support burden yet.
- `printpipe run` currently reaches input preparation and reports. It does not yet call meshgen, repair, orientation, bundling, or slicing end to end.
- HTML report is local and useful, but still a skeleton compared with a polished UI.
- Test-object coverage is fixture-level only; real non-slipper object runs remain pending.

## Next Gate

Wave 4 should migrate the slipper proof-of-concept through the new interfaces:

1. import/fixture the existing slipper artifacts without bloating the repo
2. port real mesh repair or wrap existing repair logic
3. port real Bambu profiles and 3MF generation behavior
4. port/verify slice estimate parsing against real logs
5. build an end-to-end existing-mesh pipeline path
6. compare PrintPipe outputs against the known slipper v3 artifacts

