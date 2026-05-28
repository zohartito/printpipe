from __future__ import annotations

import json
import subprocess
from pathlib import Path

from printpipe.contracts import ArtifactKind, InputKind, StageStatus
from printpipe.meshgen import (
    ExistingMeshProvider,
    Hunyuan3DProvider,
    MediaCommandMeshProvider,
    MeshGenCost,
    MeshGenError,
    MeshGenProvider,
    MeshGenRequest,
    MeshGenResult,
    MeshGenTiming,
    PlaceholderMeshProvider,
    available_provider_ids,
    default_registry,
    generate_with_retries,
    get_provider,
    register_provider,
)
from printpipe.meshgen.providers import sha256_file
from printpipe.runs.paths import create_run


def test_meshgen_request_defaults_are_local_and_bounded():
    request = MeshGenRequest(
        input_kind=InputKind.MESH,
        source_paths=(Path("part.stl"),),
    )

    assert request.output_formats == ("glb", "stl", "obj")
    assert request.quality == "standard"
    assert request.privacy_mode == "local_only"
    assert request.max_attempts == 2
    assert request.timeout_seconds == 1800
    assert request.budget_usd is None
    assert request.provider_params == {}


def test_existing_mesh_provider_imports_mesh_and_writes_receipts(tmp_path: Path):
    source = tmp_path / "fixture.stl"
    source.write_bytes(b"solid printpipe\nendsolid printpipe\n")
    layout = create_run(source, tmp_path / "runs", run_id="run-mesh")
    provider: MeshGenProvider = ExistingMeshProvider()
    request = MeshGenRequest(
        input_kind=InputKind.MESH,
        source_paths=(layout.original_input,),
        output_formats=("stl",),
    )

    result = provider.generate(request, layout)

    output_hash = sha256_file(result.normalized_mesh_path)
    assert result.status == StageStatus.SUCCEEDED
    assert result.provider_id == "existing_mesh"
    assert result.attempt_count == 1
    assert result.normalized_mesh_path.parent == layout.meshgen_dir
    assert result.normalized_mesh_path.name == "fixture.stl"
    assert result.normalized_mesh_path.read_bytes() == source.read_bytes()
    assert result.input_hashes[str(layout.original_input)] == output_hash
    assert result.output_hashes[str(result.normalized_mesh_path)] == output_hash
    assert result.cost == MeshGenCost(currency="USD", amount=0.0, estimated=False)
    assert result.timing.wall_seconds >= 0.0
    assert result.artifact.kind == ArtifactKind.GENERATED_MESH
    assert result.artifact.path == result.normalized_mesh_path

    attempts_path = layout.meshgen_dir / "attempts.jsonl"
    summary_path = layout.meshgen_dir / "summary.json"
    attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    summary = json.loads(summary_path.read_text())

    assert len(attempts) == 1
    assert attempts[0]["run_id"] == "run-mesh"
    assert attempts[0]["provider_id"] == "existing_mesh"
    assert attempts[0]["status"] == "succeeded"
    assert attempts[0]["cost"] == {"currency": "USD", "amount": 0.0, "estimated": False}
    assert attempts[0]["timing"]["wall_seconds"] >= 0.0
    assert attempts[0]["error"] is None
    assert summary["status"] == "succeeded"
    assert summary["provider_id"] == "existing_mesh"
    assert summary["artifact"]["kind"] == "generated_mesh"


def test_existing_mesh_provider_rejects_non_mesh_requests_and_logs_failure(tmp_path: Path):
    source = tmp_path / "photo.png"
    source.write_bytes(b"not a real image")
    layout = create_run(source, tmp_path / "runs", run_id="run-image")
    provider = ExistingMeshProvider()
    request = MeshGenRequest(
        input_kind=InputKind.IMAGE,
        source_paths=(layout.original_input,),
    )

    result = provider.generate(request, layout)

    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "invalid_request"
    assert result.error.retryable is False
    assert result.cost.amount == 0.0
    assert result.timing.wall_seconds >= 0.0
    assert result.normalized_mesh_path is None
    assert result.artifact is None

    attempts = [
        json.loads(line)
        for line in (layout.meshgen_dir / "attempts.jsonl").read_text().splitlines()
    ]
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["error"] == {
        "category": "invalid_request",
        "message": "existing_mesh provider only accepts mesh input",
        "retryable": False,
        "vendor_message": None,
    }
    assert attempts[0]["cost"]["amount"] == 0.0
    assert "wall_seconds" in attempts[0]["timing"]


def test_registry_exposes_existing_hunyuan3d_and_placeholder_providers():
    registry = default_registry()

    assert available_provider_ids(registry) == (
        "existing_mesh",
        "hunyuan3d",
        "media_command",
        "meshy",
        "replicate",
        "rodin",
    )
    assert get_provider("existing_mesh", registry).display_name == "Existing mesh import"
    hunyuan = get_provider("hunyuan3d", registry)
    assert hunyuan.display_name == "Hunyuan3D local command"
    assert hunyuan.capabilities.input_kinds == (
        InputKind.IMAGE,
        InputKind.GIF,
        InputKind.VIDEO,
    )
    assert hunyuan.capabilities.output_formats == ("glb", "stl", "obj")
    assert hunyuan.capabilities.supports_local is True
    assert hunyuan.capabilities.supports_cloud is False
    media_command = get_provider("media_command", registry)
    assert media_command.display_name == "Generic media meshgen command"
    assert media_command.capabilities.input_kinds == (
        InputKind.IMAGE,
        InputKind.GIF,
        InputKind.VIDEO,
    )

    custom = {}
    register_provider(ExistingMeshProvider(), custom)
    assert get_provider("existing_mesh", custom).provider_id == "existing_mesh"


def test_hunyuan3d_provider_is_disabled_until_configured(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-hunyuan-disabled")
    provider = Hunyuan3DProvider(command=())
    request = MeshGenRequest(
        input_kind=InputKind.IMAGE,
        source_paths=(layout.original_input,),
    )

    estimate = provider.estimate(request)
    health = provider.healthcheck()
    result = provider.generate(request, layout)

    assert estimate.status == StageStatus.SKIPPED
    assert estimate.cost == MeshGenCost(currency="USD", amount=0.0, estimated=False)
    assert "not configured" in estimate.message
    assert health.status == StageStatus.SKIPPED
    assert "PRINTPIPE_HUNYUAN3D_COMMAND" in health.message
    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "provider_unavailable"
    assert result.error.retryable is False

    summary = json.loads((layout.meshgen_dir / "summary.json").read_text())
    assert summary["provider_id"] == "hunyuan3d"
    assert summary["status"] == "failed"
    assert summary["error"]["category"] == "provider_unavailable"


def test_hunyuan3d_provider_runs_local_command_and_copies_output(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    command_output = tmp_path / "command-output.glb"
    calls = []

    def fake_runner(argv, *, timeout_seconds):
        calls.append((tuple(argv), timeout_seconds))
        command_output.write_bytes(b"glb mesh from local hunyuan")
        stdout = json.dumps({"output_path": str(command_output)})
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="local progress")

    layout = create_run(source, tmp_path / "runs", run_id="run-hunyuan")
    provider = Hunyuan3DProvider(command=("hunyuan3d-local",), runner=fake_runner)
    request = MeshGenRequest(
        input_kind=InputKind.IMAGE,
        source_paths=(layout.original_input,),
        output_formats=("glb",),
        prompt_hint="small slipper reference",
        seed=123,
    )

    estimate = provider.estimate(request)
    health = provider.healthcheck()
    result = provider.generate(request, layout)

    assert estimate.status == StageStatus.SUCCEEDED
    assert estimate.cost == MeshGenCost(currency="USD", amount=0.0, estimated=False)
    assert "local command" in estimate.message
    assert health.status == StageStatus.SUCCEEDED
    assert "configured" in health.message
    assert calls
    argv, timeout_seconds = calls[0]
    assert argv[0] == "hunyuan3d-local"
    assert argv[argv.index("--input-kind") + 1] == "image"
    assert argv[argv.index("--source") + 1] == str(layout.original_input)
    assert argv[argv.index("--output-format") + 1] == "glb"
    assert argv[argv.index("--prompt") + 1] == "small slipper reference"
    assert argv[argv.index("--seed") + 1] == "123"
    assert timeout_seconds == request.timeout_seconds

    assert result.status == StageStatus.SUCCEEDED
    assert result.provider_id == "hunyuan3d"
    assert result.model_id == "hunyuan3d-local-command"
    assert result.api_endpoint is None
    assert result.cost == MeshGenCost(currency="USD", amount=0.0, estimated=False)
    assert result.normalized_mesh_path == layout.meshgen_dir / "hunyuan3d.glb"
    assert result.raw_output_path == result.normalized_mesh_path
    assert result.normalized_mesh_path.read_bytes() == command_output.read_bytes()
    assert result.output_hashes[str(result.normalized_mesh_path)] == sha256_file(
        result.normalized_mesh_path
    )
    assert result.artifact.kind == ArtifactKind.GENERATED_MESH
    assert result.artifact.metadata["provider_id"] == "hunyuan3d"
    assert result.artifact.metadata["command"][0] == "hunyuan3d-local"

    summary = json.loads((layout.meshgen_dir / "summary.json").read_text())
    assert summary["provider_id"] == "hunyuan3d"
    assert summary["status"] == "succeeded"
    assert summary["cost"] == {"currency": "USD", "amount": 0.0, "estimated": False}
    assert summary["output_paths"]["normalized_mesh_path"] == "20_meshgen/hunyuan3d.glb"
    assert summary["artifact"]["metadata"]["source_output_path"] == str(command_output)


def test_media_command_provider_runs_generic_command_and_writes_receipts(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    command_output = tmp_path / "generic-output.stl"
    calls = []

    def fake_runner(argv, *, timeout_seconds):
        calls.append((tuple(argv), timeout_seconds))
        command_output.write_text("solid media\nendsolid media\n", encoding="ascii")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"output_path": str(command_output)}),
            stderr="",
        )

    layout = create_run(source, tmp_path / "runs", run_id="run-media-command")
    provider = MediaCommandMeshProvider(command=("media-meshgen",), runner=fake_runner)
    request = MeshGenRequest(
        input_kind=InputKind.IMAGE,
        source_paths=(layout.original_input,),
        output_formats=("stl",),
        prompt_hint="printable desk hook",
    )

    health = provider.healthcheck()
    result = provider.generate(request, layout)

    assert health.status == StageStatus.SUCCEEDED
    assert "Generic media meshgen command is configured" in health.message
    argv, timeout_seconds = calls[0]
    assert argv[0] == "media-meshgen"
    assert argv[argv.index("--source") + 1] == str(layout.original_input)
    assert argv[argv.index("--output-format") + 1] == "stl"
    assert argv[argv.index("--prompt") + 1] == "printable desk hook"
    assert timeout_seconds == request.timeout_seconds
    assert result.status == StageStatus.SUCCEEDED
    assert result.provider_id == "media_command"
    assert result.model_id == "generic-media-command"
    assert result.normalized_mesh_path == layout.meshgen_dir / "media_command.stl"
    assert result.artifact.label == "Generated mesh from Generic media meshgen command"

    summary = json.loads((layout.meshgen_dir / "summary.json").read_text())
    assert summary["provider_id"] == "media_command"
    assert summary["output_paths"]["normalized_mesh_path"] == "20_meshgen/media_command.stl"


def test_placeholder_providers_are_healthy_but_not_implemented(tmp_path: Path):
    source = tmp_path / "fixture.stl"
    source.write_bytes(b"mesh")
    layout = create_run(source, tmp_path / "runs", run_id="run-placeholder")
    provider: MeshGenProvider = PlaceholderMeshProvider("replicate", "Replicate")
    request = MeshGenRequest(input_kind=InputKind.MESH, source_paths=(layout.original_input,))

    estimate = provider.estimate(request)
    health = provider.healthcheck()
    result = provider.generate(request, layout)

    assert estimate.cost.estimated is True
    assert health.status == StageStatus.SKIPPED
    assert result.status == StageStatus.FAILED
    assert result.error is not None
    assert result.error.category == "provider_unavailable"
    assert result.error.retryable is False


def test_generate_with_retries_stops_after_retryable_failure_succeeds(tmp_path: Path):
    source = tmp_path / "fixture.stl"
    source.write_bytes(b"mesh")
    layout = create_run(source, tmp_path / "runs", run_id="run-retry")
    request = MeshGenRequest(
        input_kind=InputKind.MESH,
        source_paths=(layout.original_input,),
        max_attempts=2,
    )

    class FlakyProvider:
        provider_id = "flaky"
        display_name = "Flaky"

        def __init__(self) -> None:
            self.calls = 0

        def estimate(self, request: MeshGenRequest):
            raise NotImplementedError

        def healthcheck(self):
            raise NotImplementedError

        def generate(self, request: MeshGenRequest, run):
            self.calls += 1
            if self.calls == 1:
                return MeshGenResult(
                    status=StageStatus.FAILED,
                    provider_id=self.provider_id,
                    timing=MeshGenTiming(wall_seconds=0.1),
                    cost=MeshGenCost(currency="USD", amount=0.0, estimated=True),
                    attempt_count=self.calls,
                    error=MeshGenError(
                        category="transient_network",
                        message="temporary failure",
                        retryable=True,
                    ),
                )
            return MeshGenResult(
                status=StageStatus.SUCCEEDED,
                provider_id=self.provider_id,
                timing=MeshGenTiming(wall_seconds=0.2),
                cost=MeshGenCost(currency="USD", amount=0.0, estimated=True),
                attempt_count=self.calls,
            )

    provider = FlakyProvider()

    result = generate_with_retries(provider, request, layout)

    assert provider.calls == 2
    assert result.status == StageStatus.SUCCEEDED
    assert result.attempt_count == 2
