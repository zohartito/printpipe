from __future__ import annotations

import json
from pathlib import Path

from printpipe.runs.editing import (
    EditRecipe,
    EditScale,
    EditTargets,
    GeometryIntent,
    create_edit_run,
    edit_recipe_from_dict,
    load_edit_recipe,
    next_edit_run_id,
    write_edit_recipe,
)
from printpipe.runs.paths import create_run, load_run


def test_edit_recipe_json_round_trip(tmp_path: Path):
    recipe = EditRecipe(
        parent_run_id="Slipper_TPU90A_P2S_v4_wide_upper",
        scale=EditScale(overall=1.0, x=1.0, y=1.08, z=1.0),
        targets_mm=EditTargets(length=295.0, width=118.0, height=72.0),
        geometry_intent=GeometryIntent(
            upper_width_delta_mm=14.0,
            opening_width_delta_mm=12.0,
            arch_height_delta_mm=6.0,
            wall_thickness_mm=3.2,
            flat_base=True,
        ),
        support_strategy="snug_tree_auto",
        instruction="Widen the slipper upper so my foot fits without narrowing the sole.",
    )

    path = write_edit_recipe(tmp_path, recipe)
    loaded = load_edit_recipe(tmp_path)

    assert path == tmp_path / "edit_recipe.json"
    assert loaded == recipe
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "parent_run_id": "Slipper_TPU90A_P2S_v4_wide_upper",
        "scale": {"overall": 1.0, "x": 1.0, "y": 1.08, "z": 1.0},
        "targets_mm": {"length": 295.0, "width": 118.0, "height": 72.0},
        "geometry_intent": {
            "upper_width_delta_mm": 14.0,
            "opening_width_delta_mm": 12.0,
            "arch_height_delta_mm": 6.0,
            "wall_thickness_mm": 3.2,
            "flat_base": True,
        },
        "support_strategy": "snug_tree_auto",
        "instruction": "Widen the slipper upper so my foot fits without narrowing the sole.",
    }


def test_create_edit_run_references_parent_without_overwriting_original(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    parent_layout = create_run(source, tmp_path / "runs", run_id="run-slipper-001")
    original_bytes = parent_layout.original_input.read_bytes()
    recipe = EditRecipe(
        parent_run_id=parent_layout.run_id,
        scale=EditScale(y=1.08),
        targets_mm=EditTargets(length=295.0, width=118.0),
        geometry_intent=GeometryIntent(upper_width_delta_mm=14.0, flat_base=True),
        support_strategy="snug_tree_auto",
        instruction="Make the slipper upper wider, keep the sole length fixed.",
    )

    assert next_edit_run_id(parent_layout.root) == "run-slipper-001_edit_001"
    edit_layout = create_edit_run(parent_layout.root, recipe)

    assert edit_layout.run_id == "run-slipper-001_edit_001"
    assert parent_layout.original_input.read_bytes() == original_bytes
    assert load_edit_recipe(edit_layout.root) == recipe

    manifest = json.loads(edit_layout.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-slipper-001_edit_001"
    assert manifest["parent_run"] == {
        "run_id": "run-slipper-001",
        "run_root": str(parent_layout.root),
    }
    assert manifest["input"]["kind"] == "image"
    assert manifest["input"]["stored_path"] == "00_input/reference.png"
    assert manifest["edit_recipe"]["path"] == "edit_recipe.json"

    loaded_layout = load_run(edit_layout.root)
    assert loaded_layout.run_id == edit_layout.run_id
    assert loaded_layout.root == edit_layout.root
    assert loaded_layout.original_input == edit_layout.original_input
    assert loaded_layout.bundle_dir == edit_layout.bundle_dir


def test_edit_recipe_rejects_ambiguous_or_unsafe_values():
    base = {
        "schema_version": 1,
        "parent_run_id": "run-001",
        "scale": {"overall": 1.0, "x": 1.0, "y": 1.0, "z": 1.0},
        "targets_mm": {"length": 100.0, "width": 50.0, "height": None},
        "geometry_intent": {
            "upper_width_delta_mm": 0.0,
            "opening_width_delta_mm": 0.0,
            "arch_height_delta_mm": 0.0,
            "wall_thickness_mm": 2.4,
            "flat_base": True,
        },
        "support_strategy": "auto",
        "instruction": "",
    }

    missing_parent = {**base, "parent_run_id": ""}
    bad_strategy = {**base, "support_strategy": "magic"}
    bad_scale = {**base, "scale": {**base["scale"], "y": 0}}
    bad_bool = {
        **base,
        "geometry_intent": {**base["geometry_intent"], "flat_base": "maybe"},
    }

    for payload in (missing_parent, bad_strategy, bad_scale, bad_bool):
        try:
            edit_recipe_from_dict(payload)
        except ValueError:
            continue
        raise AssertionError(f"expected invalid edit recipe to fail: {payload}")

    false_recipe = edit_recipe_from_dict(
        {
            **base,
            "geometry_intent": {**base["geometry_intent"], "flat_base": "false"},
        }
    )
    assert false_recipe.geometry_intent.flat_base is False
