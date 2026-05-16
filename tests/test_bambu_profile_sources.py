from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from printpipe.bambu.profiles.sources import (
    ProfileNotFoundError,
    build_bambu_orca_filament_defaults_summary,
    copy_profile_source,
    default_bambu_orca_profile_roots,
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


def test_default_bambu_orca_profile_roots_detect_installs_and_user_ids(
    tmp_path: Path,
):
    home = tmp_path / "home"
    applications = tmp_path / "Applications"
    app_bambu_root = (
        applications
        / "BambuStudio.app"
        / "Contents"
        / "Resources"
        / "profiles"
        / "BBL"
    )
    app_orca_root = (
        applications
        / "OrcaSlicer.app"
        / "Contents"
        / "Resources"
        / "profiles"
    )
    bambu_user = (
        home
        / "Library"
        / "Application Support"
        / "BambuStudio"
        / "user"
        / "123456789012345678"
    )
    orca_default = (
        home
        / "Library"
        / "Application Support"
        / "OrcaSlicer"
        / "user"
        / "default"
    )
    for root in (app_bambu_root, app_orca_root, bambu_user, orca_default):
        (root / "filament").mkdir(parents=True)

    roots = default_bambu_orca_profile_roots(
        platform="darwin",
        home=home,
        env={"PRINTPIPE_APPLICATIONS_DIR": str(applications)},
    )

    assert roots == (
        bambu_user,
        orca_default,
        app_bambu_root,
        app_orca_root,
    )


def test_default_bambu_orca_profile_roots_honor_env_overrides(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    roots = default_bambu_orca_profile_roots(
        platform="linux",
        env={"PRINTPIPE_BAMBU_ORCA_PROFILE_ROOTS": f"{first}:{second}:{first}"},
    )

    assert roots == (first, second)


def test_build_filament_defaults_summary_is_json_friendly_and_source_priority():
    summary = build_bambu_orca_filament_defaults_summary(
        roots=[CACHE_ROOT, INSTALLED_ROOT],
    )

    json.dumps(summary)
    assert summary["searched_roots"] == [str(CACHE_ROOT), str(INSTALLED_ROOT)]
    assert summary["present_roots"] == [str(CACHE_ROOT), str(INSTALLED_ROOT)]
    assert summary["missing"] == {
        "profile_roots": False,
        "filament_defaults": False,
    }
    assert summary["profile_names_by_type"] == {
        "filament": [
            "Bambu TPU 90A @BBL P2S",
            "SUNLU TPU 90A Slipper @BBL P2S",
        ],
        "machine": ["Bambu Lab P2S 0.4 nozzle"],
        "process": ["0.20mm Slipper TPU 90A @BBL P2S"],
    }
    assert summary["filament_names_by_material"] == {
        "TPU": [
            "Bambu TPU 90A @BBL P2S",
            "SUNLU TPU 90A Slipper @BBL P2S",
        ],
    }
    assert summary["filament_defaults"] == [
        {
            "name": "SUNLU TPU 90A Slipper @BBL P2S",
            "type": "filament",
            "material": "TPU",
            "filament_type": ["TPU"],
            "source_root": str(CACHE_ROOT),
            "relative_path": "filament/SUNLU TPU 90A Slipper @BBL P2S.json",
            "path": str(CACHE_ROOT / "filament" / "SUNLU TPU 90A Slipper @BBL P2S.json"),
            "from": "User",
            "inherits": "Bambu TPU 90A @BBL P2S",
            "filament_vendor": ["SUNLU"],
        },
        {
            "name": "Bambu TPU 90A @BBL P2S",
            "type": "filament",
            "material": "TPU",
            "filament_type": ["TPU"],
            "source_root": str(INSTALLED_ROOT),
            "relative_path": "filament/Bambu TPU 90A @BBL P2S.json",
            "path": str(INSTALLED_ROOT / "filament" / "Bambu TPU 90A @BBL P2S.json"),
            "from": "system",
            "inherits": "Bambu TPU 90A @base",
            "filament_vendor": ["Bambu Lab"],
        },
    ]


def test_build_filament_defaults_summary_handles_orca_vendor_metadata(
    tmp_path: Path,
):
    root = tmp_path / "OrcaSlicer.app" / "Contents" / "Resources" / "profiles"
    filament_path = (
        root
        / "OrcaFilamentLibrary"
        / "filament"
        / "Generic PLA @System.json"
    )
    filament_path.parent.mkdir(parents=True)
    filament_path.write_text(
        json.dumps(
            {
                "name": "Generic PLA @System",
                "type": "filament",
                "from": "system",
                "filament_type": "PLA",
            }
        ),
        encoding="utf-8",
    )
    (root / "BBL.json").write_text(
        json.dumps({"vendor": "BBL"}),
        encoding="utf-8",
    )

    summary = build_bambu_orca_filament_defaults_summary(roots=[root])

    assert summary["filament_defaults"] == [
        {
            "name": "Generic PLA @System",
            "type": "filament",
            "material": "PLA",
            "filament_type": ["PLA"],
            "source_root": str(root),
            "relative_path": "OrcaFilamentLibrary/filament/Generic PLA @System.json",
            "path": str(filament_path),
            "from": "system",
            "inherits": None,
            "filament_vendor": [],
        }
    ]
    assert summary["skipped_profiles"] == [
        {
            "path": str(root / "BBL.json"),
            "source_root": str(root),
            "relative_path": "BBL.json",
            "reason": "missing name or type",
        }
    ]


def test_build_filament_defaults_summary_reports_missing_roots(tmp_path: Path):
    missing_root = tmp_path / "missing" / "profiles"

    summary = build_bambu_orca_filament_defaults_summary(roots=[missing_root])

    assert summary["searched_roots"] == [str(missing_root)]
    assert summary["present_roots"] == []
    assert summary["filament_defaults"] == []
    assert summary["missing"] == {
        "profile_roots": True,
        "filament_defaults": True,
    }
