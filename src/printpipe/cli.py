"""Command line entrypoint for PrintPipe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.contracts import InputKind
from printpipe.inputs import classify_input_path, prepare_input
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs import create_run


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

    run = subparsers.add_parser(
        "run",
        help="Create a run, prepare input artifacts, and write reports.",
    )
    run.add_argument("input", type=Path, help="Reference image, GIF, video, or mesh.")
    run.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run folders are created.",
    )
    run.add_argument(
        "--slice",
        action="store_true",
        help="Run the Bambu CLI slice gate after bundling when the input is an existing mesh.",
    )
    run.add_argument(
        "--bambu-cli",
        type=Path,
        help="Explicit Bambu Studio executable path for --slice.",
    )

    status = subparsers.add_parser(
        "status",
        help="Print a concise run status from manifest and report files.",
    )
    status.add_argument("run_root", type=Path, help="Run folder to inspect.")

    open_report = subparsers.add_parser(
        "open-report",
        help="Print the Markdown report path for a run.",
    )
    open_report.add_argument("run_root", type=Path, help="Run folder to inspect.")

    serve = subparsers.add_parser(
        "serve",
        help="Start the local web UI.",
    )
    serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for the local web server.",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the local web server.",
    )
    serve.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run folders are read and created.",
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="Check local PrintPipe environment and packaging prerequisites.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print the full doctor report as JSON.",
    )
    doctor.add_argument(
        "--platform",
        help="Override platform detection for diagnostics and tests.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"printpipe {__version__}")
        return 0

    if args.command == "init-run":
        try:
            layout = create_run(args.input, args.runs_dir)
        except FileNotFoundError:
            parser.error(f"input does not exist: {args.input}")
        except ValueError as exc:
            parser.error(str(exc))
        print(f"run id: {layout.run_id}")
        print(f"run root: {layout.root}")
        print(f"input: {layout.original_input}")
        return 0

    if args.command == "run":
        try:
            if args.bambu_cli is not None and not args.slice:
                parser.error("--bambu-cli requires --slice")
            input_kind = classify_input_path(args.input)
            if args.slice and input_kind != InputKind.MESH:
                parser.error(
                    "--slice currently requires an existing mesh input; "
                    "image/GIF/video meshgen is not wired into the orchestrator yet"
                )
            if input_kind == InputKind.MESH:
                result = run_existing_mesh_pipeline(
                    args.input,
                    args.runs_dir,
                    run_slice=args.slice,
                    slice_executable=args.bambu_cli,
                )
                layout = result.layout
                report_json = layout.reports_dir / "run_report.json"
                report_markdown = layout.reports_dir / "run_report.md"
                report_html = layout.reports_dir / "run_report.html"
            else:
                layout = create_run(args.input, args.runs_dir)
                input_result = prepare_input(layout.original_input, layout.frames_dir)
                report_dict = build_run_report_dict(layout, stages=input_result.receipts)
                report_json_artifact, report_markdown_artifact = write_run_report(
                    layout,
                    stages=input_result.receipts,
                )
                report_html_artifact = write_html_report(layout, report_dict)
                report_json = report_json_artifact.path
                report_markdown = report_markdown_artifact.path
                report_html = report_html_artifact.path
        except FileNotFoundError:
            parser.error(f"input does not exist: {args.input}")
        except PipelineError as exc:
            _print_pipeline_error(exc)
            return 2
        except ValueError as exc:
            parser.error(str(exc))
        print(f"run id: {layout.run_id}")
        print(f"run root: {layout.root}")
        print(f"input: {layout.original_input}")
        print(f"report json: {report_json}")
        print(f"report markdown: {report_markdown}")
        print(f"report html: {report_html}")
        return 0

    if args.command == "status":
        run_root = args.run_root.expanduser().resolve()
        if not run_root.exists():
            parser.error(f"run root does not exist: {args.run_root}")
        manifest_path = run_root / "manifest.json"
        report_json_path = run_root / "80_reports" / "run_report.json"
        report_markdown_path = run_root / "80_reports" / "run_report.md"
        report_html_path = run_root / "80_reports" / "run_report.html"
        manifest = _read_json_if_present(manifest_path)
        report = _read_json_if_present(report_json_path)

        run_id = _run_id(run_root, manifest, report)
        print(f"run id: {run_id}")
        print(f"run root: {run_root}")
        print(f"manifest: {'present' if manifest is not None else 'missing'}")
        print(f"input: {_input_summary(manifest)}")
        print(f"report json: {report_json_path if report_json_path.exists() else 'missing'}")
        print(f"report markdown: {report_markdown_path if report_markdown_path.exists() else 'missing'}")
        print(f"report html: {report_html_path if report_html_path.exists() else 'missing'}")
        if report is not None:
            print(f"stages: {_stage_summary(report)}")
            print(f"warnings: {len(report.get('warnings', []))}")
        else:
            print("stages: unavailable")
            print("warnings: unavailable")
        return 0

    if args.command == "open-report":
        run_root = args.run_root.expanduser().resolve()
        if not run_root.exists():
            parser.error(f"run root does not exist: {args.run_root}")
        html_report = run_root / "80_reports" / "run_report.html"
        if html_report.exists():
            print(html_report)
        else:
            print(run_root / "80_reports" / "run_report.md")
        return 0

    if args.command == "serve":
        return _serve(host=args.host, port=args.port, runs_dir=args.runs_dir)

    if args.command == "doctor":
        return _doctor(json_output=args.json, platform_name=args.platform)

    parser.print_help()
    return 0


def _serve(*, host: str, port: int, runs_dir: Path) -> int:
    from printpipe.web import server

    server.serve(host=host, port=port, runs_dir=runs_dir)
    return 0


def _doctor(*, json_output: bool, platform_name: str | None) -> int:
    from printpipe.env.doctor import build_environment_report, render_environment_report

    report = build_environment_report(platform_name=platform_name)
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_environment_report(report), end="")
    return 0


def _print_pipeline_error(error: PipelineError) -> None:
    result = error.result
    layout = result.layout
    print(f"run id: {layout.run_id}")
    print(f"run root: {layout.root}")
    print(f"input: {layout.original_input}")
    print(f"report json: {layout.reports_dir / 'run_report.json'}")
    print(f"report markdown: {layout.reports_dir / 'run_report.md'}")
    print(f"report html: {layout.reports_dir / 'run_report.html'}")
    failed_stage = _first_failed_stage(result.stages)
    if failed_stage is not None:
        print(f"failed stage: {failed_stage.stage}")
    print(f"error: {error}", file=sys.stderr)


def _first_failed_stage(stages: tuple[Any, ...]) -> Any | None:
    for stage in stages:
        if getattr(getattr(stage, "status", None), "value", None) == "failed":
            return stage
    return None


def _read_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _run_id(run_root: Path, manifest: dict[str, Any] | None, report: dict[str, Any] | None) -> str:
    if manifest and manifest.get("run_id"):
        return str(manifest["run_id"])
    if report and report.get("run_id"):
        return str(report["run_id"])
    return run_root.name


def _input_summary(manifest: dict[str, Any] | None) -> str:
    if not manifest:
        return "unknown"
    input_info = manifest.get("input", {})
    if not isinstance(input_info, dict):
        return "unknown"
    input_kind = str(input_info.get("kind", "unknown"))
    stored_path = input_info.get("stored_path")
    if stored_path:
        return f"{input_kind} ({stored_path})"
    return input_kind


def _stage_summary(report: dict[str, Any]) -> str:
    stages = report.get("stages", [])
    if not stages:
        return "none"
    parts: list[str] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        name = stage.get("stage", "unknown")
        status = stage.get("status", "unknown")
        parts.append(f"{name}={status}")
    return ", ".join(parts) if parts else "none"


if __name__ == "__main__":
    raise SystemExit(main())
