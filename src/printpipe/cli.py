"""Command line entrypoint for PrintPipe."""

from __future__ import annotations

import argparse
from pathlib import Path

from printpipe import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printpipe",
        description="Local-first reference-to-print pipeline.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show PrintPipe version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")
    init_run = subparsers.add_parser(
        "init-run",
        help="Create a run folder for an input reference.",
    )
    init_run.add_argument("input", type=Path, help="Reference image, GIF, video, or mesh.")
    init_run.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run folders are created.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"printpipe {__version__}")
        return 0

    if args.command == "init-run":
        if not args.input.exists():
            parser.error(f"input does not exist: {args.input}")
        args.runs_dir.mkdir(parents=True, exist_ok=True)
        print(f"run root: {args.runs_dir.resolve()}")
        print(f"input: {args.input.resolve()}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

