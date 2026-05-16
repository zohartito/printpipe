from __future__ import annotations

import sys
from pathlib import Path

import pytest

from printpipe.bambu.slicer import (
    SliceGateError,
    SliceResult,
    classify_slicer_output,
    gate_slice,
    parse_slice_estimate_from_text,
    run_slice_command,
)


class FakeRunLayout:
    def __init__(self, slice_dir: Path) -> None:
        self.slice_dir = slice_dir


def test_parse_slice_estimate_reads_bambu_gcode_header_patterns():
    text = """
; estimated printing time (normal mode) = 21h 30m 16s
; total filament weight [g] = 195.73
; filament cost = 3.91
; total layer number = 425
"""

    result = parse_slice_estimate_from_text(text)

    assert result.time_seconds == 77416
    assert result.filament_g == 195.73
    assert result.cost == 3.91
    assert result.layer_count == 425


def test_parse_slice_estimate_reads_markdown_summary_patterns():
    text = """
| **Total print time** | **21h 30m 16s** (77,416 s) |
| **Filament \u2014 weight** | **195.73 g** |
| **Filament cost @ $20/kg** | **$3.91** |
| Layer count | 425 |
"""

    result = parse_slice_estimate_from_text(text)

    assert result.time_seconds == 77416
    assert result.filament_g == 195.73
    assert result.cost == 3.91
    assert result.layer_count == 425


@pytest.mark.parametrize(
    ("output", "expected_error"),
    [
        ("error: mesh has non-manifold edges", "non-manifold"),
        ("warning: object has boundary edges and open contours", "boundary"),
        ("Error: part is outside the print bed boundary", "off-bed"),
        ("support_style organic will be replaced by default", "enum replacement"),
        ("Floating cantilever detected on object 1", "floating cantilever"),
    ],
)
def test_classify_slicer_output_promotes_known_slice_failures(output: str, expected_error: str):
    result = classify_slicer_output(stdout=output, stderr="", return_code=0)

    assert any(expected_error in error.lower() for error in result.errors)


def test_classify_slicer_output_keeps_unknown_warning_nonfatal():
    result = classify_slicer_output(
        stdout="WARNING: ZFiller: both point in subject",
        stderr="",
        return_code=0,
    )

    assert result.return_code == 0
    assert result.errors == ()
    assert result.warnings == ("ZFiller: both point in subject",)


def test_run_slice_command_writes_stdout_stderr_logs_and_parsed_result(tmp_path: Path):
    layout = FakeRunLayout(tmp_path / "70_slice")
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "print('; total estimated time = 1h 2m 3s'); "
            "print('; total filament weight [g] = 12.5'); "
            "print('; filament cost = 0.25'); "
            "print('; total layer count = 42'); "
            "print('minor warning', file=sys.stderr)"
        ),
    ]

    result = run_slice_command(command, layout)

    assert result.return_code == 0
    assert result.time_seconds == 3723
    assert result.filament_g == 12.5
    assert result.cost == 0.25
    assert result.layer_count == 42
    assert result.log_path == layout.slice_dir / "bambu_slice_stdout.log"
    assert (layout.slice_dir / "bambu_slice_stdout.log").read_text(encoding="utf-8").startswith(
        "; total estimated time"
    )
    assert (layout.slice_dir / "bambu_slice_stderr.log").read_text(encoding="utf-8") == "minor warning\n"


def test_run_slice_command_records_gcode_path_when_named_in_output(tmp_path: Path):
    layout = FakeRunLayout(tmp_path / "70_slice")
    gcode_path = layout.slice_dir / "plate_1.gcode"
    command = [
        sys.executable,
        "-c",
        f"from pathlib import Path; p = Path({str(gcode_path)!r}); "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text('gcode'); print(f'Exported G-code: {p}')",
    ]

    result = run_slice_command(command, layout)

    assert result.gcode_path == gcode_path


def test_gate_slice_allows_success_with_noncritical_warnings():
    result = SliceResult(return_code=0, warnings=("ZFiller: both point in subject",), errors=())

    assert gate_slice(result) is result


def test_gate_slice_rejects_hard_failure_with_clear_message():
    result = SliceResult(
        return_code=0,
        warnings=(),
        errors=("floating cantilever detected; retry orientation/support rules",),
    )

    with pytest.raises(SliceGateError, match="floating cantilever"):
        gate_slice(result)
