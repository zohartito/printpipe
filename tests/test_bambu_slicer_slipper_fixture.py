from __future__ import annotations

import json
from pathlib import Path

from printpipe.bambu.slicer import SliceResult, gate_slice, parse_slice_estimate_from_text


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bambu"
SLIPPER_SUMMARY_LOG = FIXTURE_ROOT / "slice_logs" / "slipper_v3_summary.log"
SLIPPER_EXPECTED = FIXTURE_ROOT / "slice_estimates" / "slipper_v3_expected.json"


def _load_fixture() -> tuple[str, dict]:
    text = SLIPPER_SUMMARY_LOG.read_text(encoding="utf-8")
    expected = json.loads(SLIPPER_EXPECTED.read_text(encoding="utf-8"))
    return text, expected


def test_slipper_v3_summary_fixture_parses_real_slice_estimate():
    text, payload = _load_fixture()
    expected = payload["expected"]

    result = parse_slice_estimate_from_text(text)

    assert SLIPPER_SUMMARY_LOG.stat().st_size < 2_000
    assert text.endswith("\n")
    assert "\x00" not in text
    assert "21h 30m 16s" in text
    assert "21h37 total / 195.6 g" in text
    assert result.time_seconds == expected["time_seconds"]
    assert result.filament_g == expected["filament_g"]
    assert result.cost == expected["filament_cost_usd_at_20_per_kg"]
    assert result.layer_count == expected["layer_count"]


def test_slipper_v3_summary_fixture_passes_slice_gate():
    text, payload = _load_fixture()
    expected = payload["expected"]
    parsed = parse_slice_estimate_from_text(text)
    result = SliceResult(
        return_code=expected["return_code"],
        warnings=tuple(expected["warnings"]),
        errors=tuple(expected["errors"]),
        time_seconds=parsed.time_seconds,
        filament_g=parsed.filament_g,
        layer_count=parsed.layer_count,
        cost=parsed.cost,
    )

    assert gate_slice(result) is result
