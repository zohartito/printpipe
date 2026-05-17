from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "slipper_poc_manifest.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except PermissionError:
        pytest.skip(f"external slipper artifact is not readable in this environment: {path}")
    return digest.hexdigest()


def test_slipper_manifest_has_stable_shape_and_external_artifact_paths():
    payload = _load_manifest()

    assert payload["schema_version"] == 1
    assert payload["name"] == "slipper_poc_external_artifacts"
    assert Path(payload["external_repo"]).is_absolute()
    assert len(payload["artifacts"]) >= 8

    artifact_ids = set()
    artifact_paths = set()
    required_count = 0

    for artifact in payload["artifacts"]:
        assert set(artifact) == {
            "id",
            "kind",
            "path",
            "required",
            "size_bytes",
            "sha256",
            "purpose",
        }
        assert re.match(r"^[a-z0-9_]+$", artifact["id"])
        assert artifact["id"] not in artifact_ids
        artifact_ids.add(artifact["id"])

        path = Path(artifact["path"])
        assert path.is_absolute()
        assert not path.is_relative_to(REPO_ROOT)
        assert artifact["path"] not in artifact_paths
        artifact_paths.add(artifact["path"])

        assert isinstance(artifact["kind"], str)
        assert artifact["kind"]
        assert isinstance(artifact["required"], bool)
        required_count += int(artifact["required"])
        assert isinstance(artifact["size_bytes"], int)
        assert artifact["size_bytes"] > 0
        assert SHA256_PATTERN.match(artifact["sha256"])
        assert isinstance(artifact["purpose"], str)
        assert len(artifact["purpose"]) >= 30

    assert required_count >= 6


def test_required_slipper_manifest_artifacts_exist_on_zohars_machine():
    payload = _load_manifest()
    external_repo = Path(payload["external_repo"])
    if not external_repo.exists():
        pytest.skip(f"external slipper repo is not present: {external_repo}")

    for artifact in payload["artifacts"]:
        if not artifact["required"]:
            continue

        path = Path(artifact["path"])
        assert path.exists(), f"missing required slipper artifact: {path}"
        assert path.stat().st_size == artifact["size_bytes"]
        assert _sha256(path) == artifact["sha256"]
