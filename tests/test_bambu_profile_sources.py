from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from printpipe.bambu.profiles.sources import (
    ProfileNotFoundError,
    copy_profile_source,
    discover_profile_paths,
    find_profile_source,
    load_profile_source_index,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bambu" / "profiles"
CACHE_ROOT = FIXTURE_ROOT / "cache"
INSTALLED_ROOT = FIXTURE_ROOT / "installed"


def test_discover_profile_paths_recurses_roots_in_priority_order():
    paths = discover_profile_paths([CACHE_ROOT, INSTALLED_ROOT])

    relative_paths = [path.relative_to(FIXTURE_ROOT) for path in paths]
    assert relative_paths == [
        Path("cache/filament/SUNLU TPU 90A Slipper @BBL P2S.json"),
        Path("cache/process/0.20mm Slipper TPU 90A @BBL P2S.json"),
        Path("installed/filament/Bambu TPU 90A @BBL P2S.json"),
        Path("installed/filament/SUNLU TPU 90A Slipper @BBL P2S.json"),
        Path("installed/machine/Bambu Lab P2S 0.4 nozzle.json"),
    ]


def test_load_profile_source_index_finds_profiles_by_name_and_type():
    index = load_profile_source_index([CACHE_ROOT, INSTALLED_ROOT])

    source = find_profile_source(
        index,
        name="SUNLU TPU 90A Slipper @BBL P2S",
        profile_type="filament",
    )

    assert source.name == "SUNLU TPU 90A Slipper @BBL P2S"
    assert source.type == "filament"
    assert source.source_root == CACHE_ROOT
    assert source.relative_path == Path("filament/SUNLU TPU 90A Slipper @BBL P2S.json")
    assert source.profile["from"] == "User"
    assert source.profile["inherits"] == "Bambu TPU 90A @BBL P2S"
    assert index.profiles_for_type("filament") == (
        "Bambu TPU 90A @BBL P2S",
        "SUNLU TPU 90A Slipper @BBL P2S",
    )


def test_index_preserves_source_priority_when_later_roots_have_same_profile():
    index = load_profile_source_index([CACHE_ROOT, INSTALLED_ROOT])

    source = index.find("SUNLU TPU 90A Slipper @BBL P2S", "filament")

    assert source.source_root == CACHE_ROOT
    assert source.profile["filament_vendor"] == ["SUNLU"]
    assert [match.source_root for match in index.all_matches(source.name, source.type)] == [
        CACHE_ROOT,
        INSTALLED_ROOT,
    ]


def test_find_profile_source_error_names_requested_profile_roots_and_available_names():
    index = load_profile_source_index([CACHE_ROOT, INSTALLED_ROOT])

    with pytest.raises(ProfileNotFoundError) as excinfo:
        find_profile_source(index, name="Missing TPU", profile_type="filament")

    message = str(excinfo.value)
    assert "Could not find filament profile 'Missing TPU'" in message
    assert str(CACHE_ROOT) in message
    assert str(INSTALLED_ROOT) in message
    assert "Bambu TPU 90A @BBL P2S" in message
    assert "SUNLU TPU 90A Slipper @BBL P2S" in message


def test_copy_profile_source_writes_receipt_ready_artifact(tmp_path: Path):
    index = load_profile_source_index([CACHE_ROOT, INSTALLED_ROOT])
    source = index.find("0.20mm Slipper TPU 90A @BBL P2S", "process")

    artifact = copy_profile_source(source, tmp_path / "run" / "profiles")

    expected_path = (
        tmp_path
        / "run"
        / "profiles"
        / "process"
        / "0.20mm Slipper TPU 90A @BBL P2S.json"
    )
    assert artifact.artifact_path == expected_path
    assert json.loads(expected_path.read_text(encoding="utf-8")) == source.profile
    assert artifact.sha256 == hashlib.sha256(expected_path.read_bytes()).hexdigest()
    assert artifact.as_receipt_entry() == {
        "name": "0.20mm Slipper TPU 90A @BBL P2S",
        "type": "process",
        "source_path": str(source.path),
        "artifact_path": str(expected_path),
        "sha256": artifact.sha256,
    }
