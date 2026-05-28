"""Starter template for PrintPipe media meshgen command adapters."""

from __future__ import annotations

from pathlib import Path


MEDIA_MESHGEN_COMMAND_TEMPLATE = """#!/usr/bin/env python3
\"\"\"PrintPipe media meshgen adapter template.

Fill in generate_mesh() with a real image/GIF/video-to-mesh call. PrintPipe calls
this script through PRINTPIPE_MEDIA_MESHGEN_COMMAND and expects it to write the
requested mesh to --output or print JSON with {"output_path": "..."}.
\"\"\"

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PrintPipe media meshgen adapter template."
    )
    parser.add_argument("--input-kind", required=True, choices=("image", "gif", "video"))
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--reference-image", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-format", required=True, choices=("stl", "glb", "obj"))
    parser.add_argument("--target-use", default="print")
    parser.add_argument("--quality", default="balanced")
    parser.add_argument("--prompt")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--params-json", type=Path)
    return parser


def generate_mesh(args: argparse.Namespace) -> None:
    \"\"\"Write args.output here, or replace this function with provider API calls.\"\"\"
    raise NotImplementedError(
        "Replace generate_mesh() with a real image/GIF/video-to-mesh call."
    )


def main() -> int:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        generate_mesh(args)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not args.output.exists():
        print(f"adapter did not write expected mesh: {args.output}", file=sys.stderr)
        return 2

    print(json.dumps({"output_path": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def render_media_meshgen_command_template() -> str:
    return MEDIA_MESHGEN_COMMAND_TEMPLATE


def write_media_meshgen_command_template(output_path: Path) -> Path:
    resolved = output_path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(render_media_meshgen_command_template(), encoding="utf-8")
    resolved.chmod(resolved.stat().st_mode | 0o111)
    return resolved
