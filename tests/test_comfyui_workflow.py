from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.meshgen.comfyui_workflow import inspect_comfyui_workflow


def _write_workflow(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "reference.png"},
                },
                "2": {
                    "class_type": "TripoImageToModelNode",
                    "inputs": {
                        "image": ["1", 0],
                        "model_seed": 42,
                        "texture_seed": 43,
                    },
                },
                "3": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "printable object"},
                },
                "4": {
                    "class_type": "SaveGLB",
                    "inputs": {
                        "mesh": ["2", 2],
                        "filename_prefix": "3d/PrintPipe",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_inspect_comfyui_workflow_suggests_patch_paths(tmp_path: Path):
    workflow_path = _write_workflow(tmp_path / "workflow.json")

    report = inspect_comfyui_workflow(workflow_path)

    assert report["status"] == "ready"
    assert report["has_save_glb"] is True
    assert report["save_glb_nodes"] == ["4"]
    assert report["image_patch_candidates"] == ["1.inputs.image"]
    assert report["prompt_patch_candidates"] == ["3.inputs.text"]
    assert report["seed_patch_candidates"] == [
        "2.inputs.model_seed",
        "2.inputs.texture_seed",
    ]
    assert report["suggested_params"] == {
        "comfyui_workflow": str(workflow_path),
        "comfyui_image_paths": ["1.inputs.image"],
        "comfyui_prompt_paths": ["3.inputs.text"],
        "comfyui_seed_paths": [
            "2.inputs.model_seed",
            "2.inputs.texture_seed",
        ],
    }
    assert "media-meshgen-configure" in report["configure_command"]


def test_inspect_comfyui_workflow_marks_missing_save_glb_not_ready(tmp_path: Path):
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "reference.png"},
                }
            }
        ),
        encoding="utf-8",
    )

    report = inspect_comfyui_workflow(workflow_path)

    assert report["status"] == "action_required"
    assert report["has_save_glb"] is False
    assert "SaveGLB" in report["warnings"][0]


def test_comfyui_workflow_inspect_cli_prints_json(tmp_path: Path, capsys):
    workflow_path = _write_workflow(tmp_path / "workflow.json")

    exit_code = main(["media-meshgen-comfyui-inspect", str(workflow_path), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["suggested_params"]["comfyui_workflow"] == str(workflow_path)


def test_comfyui_workflow_inspect_parser_accepts_json_flag(tmp_path: Path):
    parser = build_parser()
    workflow_path = tmp_path / "workflow.json"

    args = parser.parse_args(
        ["media-meshgen-comfyui-inspect", str(workflow_path), "--json"]
    )

    assert args.command == "media-meshgen-comfyui-inspect"
    assert args.workflow == workflow_path
    assert args.json is True
