"""Tests for the natural-language slicer intent layer (process/filament/printer)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from printpipe import mcp_server
from printpipe.pipeline import resolve_slice_settings
from printpipe.slice_intents import INTENTS, _resolve_value, list_intents, resolve_intents


@pytest.fixture(autouse=True)
def committed_profile_keyspace(monkeypatch):
    root = Path(__file__).parent / "fixtures/bambu/profiles/ci-root"
    monkeypatch.setenv("PRINTPIPE_BAMBU_PROFILE_ROOTS", str(root.resolve()))


def _first(value):
    return value[0] if isinstance(value, list) else value


def test_every_intent_key_is_a_real_keyspace_key():
    keyspace = resolve_slice_settings("Generic PLA")
    groups = (keyspace["process"], keyspace["filament"], keyspace["printer"])
    assert len(keyspace["process"]) > 100  # profiles resolved; else this guard is meaningless
    bad = {
        name: [key for key in intent.overrides if not any(key in g for g in groups)]
        for name, intent in INTENTS.items()
    }
    assert all(not missing for missing in bad.values()), bad


def test_resolve_stronger_routes_to_process_only():
    result = resolve_intents(["stronger"])
    assert result["process_overrides"]["wall_loops"] == "4"
    assert result["process_overrides"]["sparse_infill_density"] == "40%"
    assert result["filament_overrides"] == {}
    assert result["printer_overrides"] == {}
    assert result["conflicts"] == []
    assert result["unknown_keys"] == []


def test_changes_report_before_and_after_from_keyspace():
    result = resolve_intents(["draft"])
    layer = next(change for change in result["changes"] if change["key"] == "layer_height")
    assert layer["group"] == "process"
    assert layer["to"] == "0.28"
    assert layer["from"] == "0.20"  # current P2S standard, unwrapped from list form


def test_conflicting_intents_are_reported_last_wins():
    result = resolve_intents(["draft", "fine_detail"])  # both set layer_height
    assert result["process_overrides"]["layer_height"] == "0.12"  # fine_detail applied last
    conflict = next(c for c in result["conflicts"] if c["key"] == "layer_height")
    assert {setter["value"] for setter in conflict["set_by"]} == {"0.28", "0.12"}


def test_unknown_intent_is_reported_not_raised():
    result = resolve_intents(["stronger", "bogus_intent"])
    assert result["unknown_intents"] == ["bogus_intent"]
    assert result["applied_intents"] == ["stronger"]


def test_hotter_nozzle_routes_to_filament_and_resolves_relative():
    current = float(_first(resolve_slice_settings("Generic PLA")["filament"]["nozzle_temperature"]))
    result = resolve_intents(["hotter_nozzle"])
    assert result["process_overrides"] == {}
    assert result["printer_overrides"] == {}
    resolved = result["filament_overrides"]["nozzle_temperature"]
    assert [int(float(x)) for x in resolved] == [int(current) + 5] * len(resolved)


def test_hotter_bed_skips_disabled_plate_and_bumps_active():
    filament = resolve_slice_settings("Generic PLA")["filament"]
    result = resolve_intents(["hotter_bed"])
    overrides = result["filament_overrides"]
    # The engineering plate is disabled (temp 0) for PLA -> left untouched, not enabled.
    if float(_first(filament["eng_plate_temp"])) == 0:
        assert "eng_plate_temp" not in overrides
    current_hot = float(_first(filament["hot_plate_temp"]))
    resolved_hot = overrides["hot_plate_temp"]
    assert [int(float(x)) for x in resolved_hot] == [int(current_hot) + 5] * len(resolved_hot)


def test_quiet_routes_to_printer_and_halves_acceleration():
    current = [float(x) for x in resolve_slice_settings("Generic PLA")["printer"]["machine_max_acceleration_x"]]
    result = resolve_intents(["quiet"])
    assert result["filament_overrides"] == {}
    resolved = [float(x) for x in result["printer_overrides"]["machine_max_acceleration_x"]]
    assert resolved == [value * 0.5 for value in current]


def test_cooler_nozzle_resolves_relative_subtract():
    current = float(_first(resolve_slice_settings("Generic PLA")["filament"]["nozzle_temperature"]))
    resolved = resolve_intents(["cooler_nozzle"])["filament_overrides"]["nozzle_temperature"]
    assert [int(float(x)) for x in resolved] == [int(current) - 5] * len(resolved)


def test_cross_group_intent_set_routes_each_key_simultaneously():
    result = resolve_intents(["stronger", "hotter_nozzle", "quiet"])
    assert "wall_loops" in result["process_overrides"]
    assert "nozzle_temperature" in result["filament_overrides"]
    assert "machine_max_acceleration_x" in result["printer_overrides"]
    assert result["conflicts"] == []
    assert result["unknown_keys"] == []
    seen = (
        list(result["process_overrides"])
        + list(result["filament_overrides"])
        + list(result["printer_overrides"])
    )
    assert len(seen) == len(set(seen))  # no key routed to more than one group


def test_resolve_value_absolute_and_unresolved_edges():
    assert _resolve_value("", "100") == ("set", "")  # empty string is absolute, no IndexError
    assert _resolve_value("40%", "15%") == ("set", "40%")  # non-numeric absolute passes through
    assert _resolve_value("+5", None) == ("unresolved", None)  # relative vs missing value
    assert _resolve_value("-5", ["enabled"]) == ("unresolved", None)  # relative vs non-numeric
    assert _resolve_value("+5", ["0"]) == ("noop", None)  # disabled setting left untouched


def test_hotter_and_cooler_nozzle_conflict_last_wins():
    result = resolve_intents(["hotter_nozzle", "cooler_nozzle"])  # cooler applied last
    conflict = next(c for c in result["conflicts"] if c["key"] == "nozzle_temperature")
    assert conflict["group"] == "filament"
    assert len(conflict["set_by"]) == 2


def test_list_intents_exposes_curated_vocabulary():
    names = {intent["name"] for intent in list_intents()}
    assert {"stronger", "draft", "needs_supports", "hotter_bed", "quiet"} <= names


def test_mcp_list_and_resolve_tools_round_trip():
    listed = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_slice_intents", "arguments": {}},
        }
    )
    names = {i["name"] for i in json.loads(listed["result"]["content"][0]["text"])["intents"]}
    assert "hotter_bed" in names

    resolved = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "resolve_slice_intents",
                "arguments": {"intents": ["needs_supports", "hotter_nozzle"]},
            },
        }
    )
    payload = json.loads(resolved["result"]["content"][0]["text"])
    assert payload["process_overrides"]["enable_support"] == "1"
    assert "nozzle_temperature" in payload["filament_overrides"]
