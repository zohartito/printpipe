"""Stage 0 kill-switch: parametric code-CAD provider produces print-clean geometry."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from printpipe.contracts import ArtifactKind, InputKind, StageStatus
from printpipe.geometry.artifacts import _read_ascii_stl_triangles
from printpipe.meshgen import (
    available_provider_ids,
    build_media_meshgen_readiness,
    default_registry,
    get_provider,
)
from printpipe.meshgen.contracts import MeshGenProvider, MeshGenRequest
from printpipe.meshgen.parametric_cad import ParametricCadProvider
from printpipe.runs.paths import create_prompt_run


def _request() -> MeshGenRequest:
    return MeshGenRequest(
        input_kind=InputKind.PROMPT,
        source_paths=(),
        prompt_hint="a 40x15x3 mm flat coupon",
        output_formats=("stl",),
        max_attempts=1,
    )


def _layout(tmp_path: Path, run_id: str):
    return create_prompt_run("a 40x15x3 mm flat coupon", tmp_path / "runs", run_id=run_id)


def test_provider_satisfies_meshgen_protocol() -> None:
    assert isinstance(ParametricCadProvider(), MeshGenProvider)


def test_registered_and_selectable_in_default_registry() -> None:
    assert "parametric_cad" in available_provider_ids()
    provider = get_provider("parametric_cad", default_registry())
    assert provider.provider_id == "parametric_cad"
    assert provider.capabilities.output_formats == ("stl",)


def test_generate_writes_watertight_manifold_ascii_stl(tmp_path: Path) -> None:
    layout = _layout(tmp_path, "run-cad-box")
    result = ParametricCadProvider().generate(_request(), layout)

    assert result.status == StageStatus.SUCCEEDED
    assert result.artifact is not None
    assert result.artifact.kind == ArtifactKind.GENERATED_MESH
    stl_path = Path(result.artifact.path)
    assert stl_path.parent == layout.meshgen_dir
    assert stl_path.suffix == ".stl"

    raw = stl_path.read_bytes()
    assert b"\x00" not in raw, "must be ASCII STL (no binary)"
    assert raw.decode("ascii").lstrip().lower().startswith("solid")

    # PrintPipe's own reader must accept it -> 12 triangles for a box.
    triangles = _read_ascii_stl_triangles(stl_path)
    assert len(triangles) == 12

    # Watertight + edge-manifold: every undirected edge shared by exactly 2 faces.
    edges: Counter[tuple] = Counter()
    for tri in triangles:
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            edges[frozenset((a, b))] += 1
    assert edges, "box must have edges"
    assert all(count == 2 for count in edges.values()), "non-manifold edge detected"
    assert len(edges) == 18, "a triangulated box has 18 unique edges"

    # 8 unique corner vertices, dimensioned exactly as requested.
    corners = {v for tri in triangles for v in tri}
    assert len(corners) == 8
    xs = sorted({round(v[0], 6) for v in corners})
    ys = sorted({round(v[1], 6) for v in corners})
    zs = sorted({round(v[2], 6) for v in corners})
    assert xs == [0.0, 40.0] and ys == [0.0, 15.0] and zs == [0.0, 3.0]


def test_generate_writes_provider_receipts(tmp_path: Path) -> None:
    layout = _layout(tmp_path, "run-cad-receipts")
    ParametricCadProvider().generate(_request(), layout)
    summary = json.loads((layout.meshgen_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["provider_id"] == "parametric_cad"
    assert summary["status"] == "succeeded"


def test_custom_dimensions_are_honored(tmp_path: Path) -> None:
    layout = _layout(tmp_path, "run-cad-dims")
    request = MeshGenRequest(
        input_kind=InputKind.PROMPT,
        source_paths=(),
        output_formats=("stl",),
        provider_params={"box_mm": [20.0, 10.0, 5.0]},
        max_attempts=1,
    )
    result = ParametricCadProvider().generate(request, layout)
    triangles = _read_ascii_stl_triangles(Path(result.artifact.path))
    corners = {v for tri in triangles for v in tri}
    xs = sorted({round(v[0], 6) for v in corners})
    zs = sorted({round(v[2], 6) for v in corners})
    assert xs == [0.0, 20.0] and zs == [0.0, 5.0]


def test_does_not_count_as_live_media_meshgen_provider() -> None:
    # The provider must not flip the image/GIF/video readiness gate: it emits a
    # parametric primitive, it does not reconstruct a reference image.
    readiness = build_media_meshgen_readiness(registry=default_registry())
    summary = next(
        item for item in readiness["providers"] if item["provider_id"] == "parametric_cad"
    )
    assert summary["supports_media"] is False
    assert readiness["live_media_provider_count"] == 0
