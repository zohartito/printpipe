from __future__ import annotations

import json
import re
from pathlib import Path

from printpipe.mesh.validate import validate_mesh_topology


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
TOPOLOGY_ROOT = FIXTURE_ROOT / "meshes" / "topology"
SLICE_LOG_ROOT = FIXTURE_ROOT / "bambu" / "slice_logs"

TOPOLOGY_FIXTURES = {
    "watertight_tetrahedron.json": {
        "vertices_count": 4,
        "faces": 4,
        "passed": True,
        "watertight": True,
        "boundary_edges": 0,
        "non_manifold_edges": 0,
    },
    "open_mesh_boundary.json": {
        "vertices_count": 3,
        "faces": 1,
        "passed": False,
        "watertight": False,
        "boundary_edges": 3,
        "non_manifold_edges": 0,
    },
    "non_manifold_edge.json": {
        "vertices_count": 5,
        "faces": 3,
        "passed": False,
        "watertight": False,
        "boundary_edges": 6,
        "non_manifold_edges": 1,
    },
}

SLICE_LOG_FIXTURES = {
    "non_manifold_warning.log": ("non_manifold", "non-manifold"),
    "boundary_off_bed_warning.log": ("off_bed", "outside the printable area"),
    "enum_replacement_warning.log": ("enum_replacement", "support_style"),
    "floating_cantilever_warning.log": ("floating_cantilever", "floating cantilever"),
    "success_estimate.log": ("success", "estimated printing time"),
}


def test_topology_json_fixtures_are_small_parseable_and_match_expected_stats():
    for filename, expected in TOPOLOGY_FIXTURES.items():
        path = TOPOLOGY_ROOT / filename

        assert path.stat().st_size < 2_000
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = validate_mesh_topology(
            payload["faces"],
            vertices_count=payload["vertices_count"],
        )

        assert set(payload) == {"description", "vertices_count", "faces", "expected"}
        assert len(payload["description"]) > 20
        assert len(payload["faces"]) == expected["faces"]
        assert payload["expected"] == expected
        assert result.passed is expected["passed"]
        assert result.stats.vertices == expected["vertices_count"]
        assert result.stats.faces == expected["faces"]
        assert result.stats.watertight is expected["watertight"]
        assert result.stats.boundary_edges == expected["boundary_edges"]
        assert result.stats.non_manifold_edges == expected["non_manifold_edges"]


def test_slicer_log_fixtures_are_small_text_and_have_parseable_expectations():
    for filename, (expected_kind, expected_phrase) in SLICE_LOG_FIXTURES.items():
        path = SLICE_LOG_ROOT / filename
        text = path.read_text(encoding="utf-8")

        assert path.stat().st_size < 2_000
        assert text.endswith("\n")
        assert "\x00" not in text
        assert re.search(r"^EXPECT: [a-z_]+$", text, flags=re.MULTILINE)
        assert f"EXPECT: {expected_kind}" in text
        assert expected_phrase in text.lower()
        assert len(text.splitlines()) <= 8
