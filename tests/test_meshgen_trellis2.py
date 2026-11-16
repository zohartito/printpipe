"""TRELLIS.2 media meshgen provider: selection, command shape, honest failures, readiness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from printpipe.beta.readiness import build_beta_readiness_report
from printpipe.contracts import InputKind, StageStatus
from printpipe.final_plan import _tested_media_command_action
from printpipe.meshgen import (
    MediaCommandMeshProvider,
    MeshGenRequest,
    TRELLIS2_COMMAND_ENV,
    Trellis2Provider,
    build_media_meshgen_readiness,
    default_registry,
    get_provider,
)
from printpipe.meshgen.smoke import (
    _smoke_provider,
    build_media_meshgen_smoke_status,
    run_media_meshgen_smoke,
)
from printpipe.pipeline import _default_media_meshgen_provider
from printpipe.runs.paths import create_run


FIXTURE_STL = (
    Path(__file__).parent
    / "fixtures"
    / "objects"
    / "existing_stl_pipeline"
    / "tiny_tetrahedron.stl"
)
OTHER_COMMAND_ENVS = (
    "PRINTPIPE_MEDIA_MESHGEN_COMMAND",
    "PRINTPIPE_HUNYUAN3D_COMMAND",
    "PRINTPIPE_CONFIG_PATH",
    "PRINTPIPE_TRUST_PROJECT_MEDIA_COMMAND",
)


@pytest.fixture
def clean_provider_env(monkeypatch):
    for name in (*OTHER_COMMAND_ENVS, "PRINTPIPE_TRELLIS2_COMMAND"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _image_request(layout, *, output_format: str = "stl") -> MeshGenRequest:
    return MeshGenRequest(
        input_kind=InputKind.IMAGE,
        source_paths=(layout.original_input,),
        output_formats=(output_format,),
        seed=7,
    )


def _layout(tmp_path: Path, run_id: str):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    return create_run(source, tmp_path / "runs", run_id=run_id)


def test_trellis2_env_name_and_registry_entry():
    assert TRELLIS2_COMMAND_ENV == "PRINTPIPE_TRELLIS2_COMMAND"
    provider = get_provider("trellis2", default_registry())
    assert isinstance(provider, Trellis2Provider)
    assert provider.display_name == "TRELLIS.2 image-to-3D command"
    assert provider.model_id == "microsoft/TRELLIS.2-4B"
    assert provider.capabilities.input_kinds == (
        InputKind.IMAGE,
        InputKind.GIF,
        InputKind.VIDEO,
    )
    assert provider.capabilities.output_formats == ("glb", "stl", "obj")
    assert provider.capabilities.supports_local is True
    assert provider.capabilities.supports_cloud is False


def test_trellis2_provider_is_disabled_until_configured(tmp_path: Path, clean_provider_env):
    layout = _layout(tmp_path, "run-trellis2-disabled")
    provider = Trellis2Provider(command=())

    health = provider.healthcheck()
    result = provider.generate(_image_request(layout), layout)

    assert health.status == StageStatus.SKIPPED
    assert "PRINTPIPE_TRELLIS2_COMMAND" in health.message
    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "provider_unavailable"
    assert not (layout.meshgen_dir / "trellis2.stl").exists()
    summary = json.loads((layout.meshgen_dir / "summary.json").read_text())
    assert summary["provider_id"] == "trellis2"
    assert summary["status"] == "failed"


def test_trellis2_provider_builds_runner_command(tmp_path: Path):
    layout = _layout(tmp_path, "run-trellis2-command")
    calls = []

    def fake_runner(argv, *, timeout_seconds):
        calls.append((tuple(argv), timeout_seconds))
        output = Path(argv[argv.index("--output") + 1])
        output.write_bytes(FIXTURE_STL.read_bytes())
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="trellis progress")

    provider = Trellis2Provider(
        command="python -m printpipe.meshgen.trellis2 --remote gpu-host",
        runner=fake_runner,
    )
    request = _image_request(layout)
    result = provider.generate(request, layout)

    argv, timeout_seconds = calls[0]
    assert argv[:5] == (
        "python",
        "-m",
        "printpipe.meshgen.trellis2",
        "--remote",
        "gpu-host",
    )
    assert argv[argv.index("--input-kind") + 1] == "image"
    assert argv[argv.index("--output") + 1] == str(layout.meshgen_dir / "trellis2.stl")
    assert argv[argv.index("--output-format") + 1] == "stl"
    assert argv[argv.index("--source") + 1] == str(layout.original_input)
    assert argv[argv.index("--seed") + 1] == "7"
    assert timeout_seconds == request.timeout_seconds
    assert result.status == StageStatus.SUCCEEDED
    assert result.provider_id == "trellis2"
    assert result.model_id == "microsoft/TRELLIS.2-4B"
    assert result.normalized_mesh_path == layout.meshgen_dir / "trellis2.stl"
    assert result.normalized_mesh_path.read_bytes() == FIXTURE_STL.read_bytes()


def test_trellis2_provider_reports_nonzero_exit_honestly(tmp_path: Path):
    layout = _layout(tmp_path, "run-trellis2-nonzero")

    def failing_runner(argv, *, timeout_seconds):
        return subprocess.CompletedProcess(
            argv,
            3,
            stdout="",
            stderr="TRELLIS.2 model unavailable: gated Hugging Face dependency",
        )

    provider = Trellis2Provider(command=("trellis2-runner",), runner=failing_runner)
    result = provider.generate(_image_request(layout), layout)

    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "provider_command_failed"
    assert "exited with code 3" in result.error.message
    assert "gated Hugging Face dependency" in (result.error.vendor_message or "")
    assert result.normalized_mesh_path is None
    assert not (layout.meshgen_dir / "trellis2.stl").exists()
    summary = json.loads((layout.meshgen_dir / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["error"]["category"] == "provider_command_failed"


def test_trellis2_provider_reports_missing_output_honestly(tmp_path: Path):
    layout = _layout(tmp_path, "run-trellis2-missing")

    def silent_runner(argv, *, timeout_seconds):
        return subprocess.CompletedProcess(argv, 0, stdout="done", stderr="")

    provider = Trellis2Provider(command=("trellis2-runner",), runner=silent_runner)
    result = provider.generate(_image_request(layout), layout)

    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "provider_output_missing"
    assert result.normalized_mesh_path is None


def test_pipeline_and_smoke_select_trellis2_when_only_its_env_is_set(clean_provider_env):
    clean_provider_env.setenv("PRINTPIPE_TRELLIS2_COMMAND", "trellis2-runner --remote pc")

    pipeline_provider = _default_media_meshgen_provider()
    smoke_provider = _smoke_provider(command=None, config_cwd=None)

    assert isinstance(pipeline_provider, Trellis2Provider)
    assert pipeline_provider.command == ("trellis2-runner", "--remote", "pc")
    assert isinstance(smoke_provider, Trellis2Provider)


def test_generic_media_command_keeps_precedence_over_trellis2(clean_provider_env):
    clean_provider_env.setenv("PRINTPIPE_TRELLIS2_COMMAND", "trellis2-runner")
    clean_provider_env.setenv("PRINTPIPE_MEDIA_MESHGEN_COMMAND", "generic-adapter")

    provider = _default_media_meshgen_provider()

    assert isinstance(provider, MediaCommandMeshProvider)
    assert not isinstance(provider, Trellis2Provider)


def test_doctor_readiness_lists_trellis2_as_not_configured():
    readiness = build_media_meshgen_readiness(env={})

    entry = next(item for item in readiness["providers"] if item["provider_id"] == "trellis2")
    assert entry["status"] == "skipped"
    assert "PRINTPIPE_TRELLIS2_COMMAND" in entry["message"]
    assert readiness["overall_status"] == "action_required"


def test_configured_trellis2_stays_not_ready_without_smoke_receipt(tmp_path: Path):
    readiness = build_media_meshgen_readiness(
        env={"PRINTPIPE_TRELLIS2_COMMAND": "trellis2-runner --remote pc"}
    )
    entry = next(item for item in readiness["providers"] if item["provider_id"] == "trellis2")
    assert entry["status"] == "succeeded"
    assert readiness["live_media_provider_count"] == 1

    runs_dir = tmp_path / "runs"
    report = build_beta_readiness_report(
        runs_dir,
        environment_report={"meshgen": readiness},
        media_meshgen_smoke_status=build_media_meshgen_smoke_status(runs_dir),
    )

    gate = {item["id"]: item for item in report["gates"]}["media_meshgen"]
    assert gate["status"] == "action_required"
    assert "no successful smoke receipt" in gate["detail"]
    assert report["overall_status"] == "action_required"


def test_failed_trellis2_smoke_does_not_satisfy_readiness(tmp_path: Path, clean_provider_env):
    failing_runner = tmp_path / "failing_trellis2.py"
    failing_runner.write_text(
        "import sys\n"
        "sys.stderr.write('TRELLIS.2 model unavailable: no CUDA\\n')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    command = f"{sys.executable} {failing_runner}"
    clean_provider_env.setenv("PRINTPIPE_TRELLIS2_COMMAND", command)
    source = tmp_path / "reference.png"
    _write_png(source)
    runs_dir = tmp_path / "smoke-runs"

    payload = run_media_meshgen_smoke(source, runs_dir=runs_dir)
    status = build_media_meshgen_smoke_status(runs_dir)

    assert payload["provider_id"] == "trellis2"
    assert payload["status"] == "failed"
    assert payload["command"] == command
    assert "output_path" not in payload
    assert status["overall_status"] == "missing"
    assert status["failed_smoke_count"] == 1


def test_successful_trellis2_smoke_records_receipt_and_env_handoff(
    tmp_path: Path,
    clean_provider_env,
):
    fake_runner = tmp_path / "fake_trellis2.py"
    fake_runner.write_text(
        "import argparse, shutil\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--output', required=True)\n"
        "args, _ = parser.parse_known_args()\n"
        f"shutil.copyfile({str(FIXTURE_STL)!r}, args.output)\n",
        encoding="utf-8",
    )
    command = f"{sys.executable} {fake_runner}"
    clean_provider_env.setenv("PRINTPIPE_TRELLIS2_COMMAND", command)
    source = tmp_path / "reference.png"
    _write_png(source)
    runs_dir = tmp_path / "smoke-runs"

    payload = run_media_meshgen_smoke(source, runs_dir=runs_dir)
    status = build_media_meshgen_smoke_status(runs_dir)
    action = _tested_media_command_action(
        runs_path=runs_dir,
        smoke_status=status,
        detail="Media provider not configured.",
    )

    assert payload["status"] == "succeeded"
    assert payload["provider_id"] == "trellis2"
    assert payload["output_path"] == "20_meshgen/trellis2.stl"
    assert status["overall_status"] == "passed"
    assert action is not None
    assert action["start_command"].startswith("export PRINTPIPE_TRELLIS2_COMMAND=")


def _write_png(path: Path) -> None:
    # The smoke path copies the reference without decoding it (same as the
    # existing smoke tests), so placeholder bytes are enough here.
    path.write_bytes(b"fake image")


@pytest.fixture
def fake_trellis_worker(monkeypatch):
    """Stub GPU inference while exercising the real worker and mesh exporters."""
    from printpipe.meshgen import trellis2_worker

    cuda = SimpleNamespace(
        is_available=lambda: True,
        get_device_name=lambda _: "fake CUDA device",
        reset_peak_memory_stats=lambda: None,
        max_memory_allocated=lambda: 0,
        max_memory_reserved=lambda: 0,
        OutOfMemoryError=type("OutOfMemoryError", (RuntimeError,), {}),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    monkeypatch.setitem(
        sys.modules, "PIL",
        SimpleNamespace(Image=SimpleNamespace(open=lambda _: SimpleNamespace(load=lambda: None))),
    )

    def install(textured):
        mesh = SimpleNamespace(
            vertices=None, faces=None, attrs=None, coords=None, layout=None,
            voxel_size=1, simplify=lambda _: None,
        )
        pipeline = SimpleNamespace(cuda=lambda: None, run=lambda *a, **kw: [mesh])
        pipelines = SimpleNamespace(
            Trellis2ImageTo3DPipeline=SimpleNamespace(from_pretrained=lambda _: pipeline)
        )
        monkeypatch.setitem(sys.modules, "trellis2", SimpleNamespace(pipelines=pipelines))
        monkeypatch.setitem(sys.modules, "trellis2.pipelines", pipelines)
        monkeypatch.setitem(
            sys.modules, "o_voxel",
            SimpleNamespace(postprocess=SimpleNamespace(to_glb=lambda **kw: textured)),
        )
        return trellis2_worker

    return install


@pytest.mark.parametrize("target_size_mm", [80.0, 123.5])
@pytest.mark.parametrize("source_size", [0.5, 1.0])
def test_scale_vertices_preserves_proportions_and_origin_without_mutation(target_size_mm, source_size):
    np = pytest.importorskip("numpy")
    from printpipe.meshgen import trellis2_worker

    vertices = np.array([[-0.5, -0.125, 0.125], [0.5, 0.375, 0.375]]) * source_size
    original = vertices.copy()

    scaled, factor, bbox_size_mm = trellis2_worker._scale_vertices(vertices, target_size_mm)

    np.testing.assert_array_equal(vertices, original)
    np.testing.assert_allclose(scaled, original * (target_size_mm / source_size))
    assert factor == pytest.approx(target_size_mm / source_size)
    assert bbox_size_mm == pytest.approx([target_size_mm, target_size_mm / 2, target_size_mm / 4])


@pytest.mark.parametrize("output_format", ["stl", "obj", "glb"])
@pytest.mark.parametrize("target_size_mm", [None, 123.5])
def test_worker_exports_mesh_at_target_size(
    tmp_path: Path, fake_trellis_worker, output_format, target_size_mm,
):
    trimesh = pytest.importorskip("trimesh")
    textured = trimesh.creation.box(extents=(1, 0.5, 0.25))
    textured.apply_translation((0, 0.125, 0.25))
    original_bounds = textured.bounds.copy()
    worker = fake_trellis_worker(textured)
    output = tmp_path / "mesh" / f"model.{output_format}"
    result_path = tmp_path / "result.json"
    argv = [
        "--input", str(tmp_path / "reference.png"), "--output", str(output),
        "--output-format", output_format, "--result", str(result_path),
    ]
    if target_size_mm is not None:
        argv += ["--target-size-mm", str(target_size_mm)]

    assert worker.main(argv) == 0

    expected_size = 80.0 if target_size_mm is None else target_size_mm
    exported = trimesh.load(output, force="mesh", process=False)
    assert exported.extents == pytest.approx([expected_size, expected_size / 2, expected_size / 4])
    assert exported.bounds == pytest.approx(original_bounds * expected_size)
    result = json.loads(result_path.read_text())
    assert result["status"] == "succeeded"
    assert result["scale_factor"] == pytest.approx(expected_size)
    assert result["bbox_size_mm"] == pytest.approx(exported.extents.tolist())
    assert result["vertex_count"] == len(textured.vertices)
    assert result["face_count"] == len(textured.faces)
    assert result["watertight"] is True


@pytest.mark.parametrize("output_format", ["stl", "obj", "glb"])
@pytest.mark.parametrize("invalid_mesh", ["zero", "nan", "inf", "empty"])
def test_worker_rejects_unusable_mesh_before_export(
    tmp_path: Path, fake_trellis_worker, output_format, invalid_mesh,
):
    np = pytest.importorskip("numpy")
    pytest.importorskip("trimesh")
    vertices = np.zeros((0 if invalid_mesh == "empty" else 3, 3))
    if invalid_mesh in ("nan", "inf"):
        vertices[0, 1] = float(invalid_mesh)
    textured = SimpleNamespace(
        vertices=vertices, faces=np.array([[0, 1, 2]]),
        export=lambda *a, **kw: pytest.fail("unusable mesh must not be exported"),
    )
    worker = fake_trellis_worker(textured)
    output = tmp_path / "mesh" / f"model.{output_format}"
    result_path = tmp_path / "result.json"

    code = worker.main([
        "--input", str(tmp_path / "reference.png"), "--output", str(output),
        "--output-format", output_format, "--result", str(result_path),
    ])

    assert code == worker.EXIT_OUTPUT_MISSING == 5
    assert not output.parent.exists()
    result = json.loads(result_path.read_text())
    assert result["status"] == "failed"
    assert "no usable mesh" in result["error"]
    assert "scale_factor" not in result
