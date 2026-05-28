"""Command line entrypoint for PrintPipe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.contracts import InputKind
from printpipe.inputs import classify_input_path
from printpipe.local_open import open_run_folder
from printpipe.pipeline import (
    PipelineError,
    run_edit_recipe_pipeline,
    run_existing_mesh_pipeline,
    run_prompt_pipeline,
)
from printpipe.runs import create_run, load_run


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
    run.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Reference image, GIF, video, or mesh. Omit when using --prompt.",
    )
    run.add_argument(
        "--prompt",
        help="Prompt text to use with a reference input, or by itself with a configured prompt-image command.",
    )
    run.add_argument(
        "--prompt-image-provider",
        choices=("auto", "command", "openai"),
        default="auto",
        help="Prompt-only reference image provider. auto uses a configured command first, then OpenAI when OPENAI_API_KEY is set.",
    )
    run.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run folders are created.",
    )
    run.add_argument(
        "--material",
        default="Generic PLA",
        help="Material/filament label for reports and pre-print checklist.",
    )
    run.add_argument(
        "--printer",
        default="Bambu Lab P2S",
        help="Printer label for reports and pre-print checklist.",
    )
    run.add_argument(
        "--use-case",
        default="print",
        help="Use-case label for reports and pre-print checklist.",
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

    open_folder = subparsers.add_parser(
        "open-folder",
        help="Open a local run, report, or bundle folder.",
    )
    open_folder.add_argument("run_root", type=Path, help="Run folder to open from.")
    open_folder.add_argument(
        "--target",
        choices=("run", "report", "bundle"),
        default="run",
        help="Which local folder to open.",
    )
    open_folder.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the target folder without opening Finder/Explorer.",
    )

    rebuild_edit = subparsers.add_parser(
        "rebuild-edit",
        help="Rebuild a non-destructive edit run from edit_recipe.json.",
    )
    rebuild_edit.add_argument("run_root", type=Path, help="Edit run folder to rebuild.")
    rebuild_edit.add_argument(
        "--slice",
        action="store_true",
        help="Run the Bambu CLI slice gate after rebuilding.",
    )
    rebuild_edit.add_argument(
        "--bambu-cli",
        type=Path,
        help="Explicit Bambu Studio executable path for --slice.",
    )

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

    package_smoke = subparsers.add_parser(
        "package-smoke",
        help="Run or describe local packaging smoke checks.",
    )
    package_smoke.add_argument(
        "--platform",
        choices=("macos", "windows"),
        default="macos",
        help="Platform smoke path to run.",
    )
    package_smoke.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Directory where package-smoke run folders are created.",
    )
    package_smoke.add_argument(
        "--plan",
        action="store_true",
        help="Print the smoke plan without running the pipeline.",
    )
    package_smoke.add_argument(
        "--json",
        action="store_true",
        help="Print package-smoke output as JSON.",
    )

    build_zipapp = subparsers.add_parser(
        "build-zipapp",
        help="Build a portable printpipe.pyz artifact.",
    )
    build_zipapp.add_argument(
        "--output",
        type=Path,
        default=Path("dist/printpipe.pyz"),
        help="Path for the generated zipapp artifact.",
    )
    build_zipapp.add_argument(
        "--json",
        action="store_true",
        help="Print zipapp build output as JSON.",
    )

    build_macos_app = subparsers.add_parser(
        "build-macos-app",
        help="Build an unsigned PrintPipe.app wrapper around the zipapp.",
    )
    build_macos_app.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipe.app"),
        help="Path for the generated .app bundle.",
    )
    build_macos_app.add_argument(
        "--json",
        action="store_true",
        help="Print app bundle build output as JSON.",
    )
    build_macos_app.add_argument(
        "--adhoc-sign",
        action="store_true",
        help="Apply a local ad-hoc codesign signature; this is not notarization.",
    )
    build_macos_app.add_argument(
        "--developer-id-identity",
        help="Developer ID Application identity to use for distribution signing.",
    )

    build_macos_standalone = subparsers.add_parser(
        "build-macos-standalone",
        help="Build a PyInstaller macOS app with a bundled Python runtime.",
    )
    build_macos_standalone.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipeStandalone.app"),
        help="Path for the generated standalone .app bundle.",
    )
    build_macos_standalone.add_argument(
        "--pyinstaller",
        default=os.environ.get("PRINTPIPE_PYINSTALLER", "pyinstaller"),
        help=(
            "PyInstaller command to run. Use "
            "'uvx --from pyinstaller pyinstaller' when pyinstaller is not on PATH."
        ),
    )
    build_macos_standalone.add_argument(
        "--json",
        action="store_true",
        help="Print standalone app build output as JSON.",
    )
    build_macos_standalone.add_argument(
        "--adhoc-sign",
        action="store_true",
        help="Ad-hoc sign the PyInstaller app; this is not Developer ID notarization.",
    )

    build_macos_dmg = subparsers.add_parser(
        "build-macos-dmg",
        help="Build a drag-install DMG containing PrintPipe.app.",
    )
    build_macos_dmg.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipe.dmg"),
        help="Path for the generated .dmg artifact.",
    )
    build_macos_dmg.add_argument(
        "--json",
        action="store_true",
        help="Print DMG build output as JSON.",
    )
    build_macos_dmg.add_argument(
        "--adhoc-sign",
        action="store_true",
        help="Ad-hoc sign the embedded app before creating the DMG.",
    )
    build_macos_dmg.add_argument(
        "--developer-id-identity",
        help="Developer ID Application identity to sign the embedded app.",
    )
    build_macos_dmg.add_argument(
        "--notary-profile",
        help="Keychain profile name for xcrun notarytool submit --wait.",
    )

    build_windows_portable = subparsers.add_parser(
        "build-windows-portable",
        help="Build a portable Windows ZIP containing printpipe.pyz and launchers.",
    )
    build_windows_portable.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipe-Windows-portable.zip"),
        help="Path for the generated Windows portable ZIP.",
    )
    build_windows_portable.add_argument(
        "--json",
        action="store_true",
        help="Print Windows portable package output as JSON.",
    )

    build_windows_standalone = subparsers.add_parser(
        "build-windows-standalone",
        help="Build a PyInstaller Windows ZIP with a bundled Python runtime.",
    )
    build_windows_standalone.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipe-Windows-standalone.zip"),
        help="Path for the generated Windows standalone ZIP.",
    )
    build_windows_standalone.add_argument(
        "--pyinstaller",
        default=os.environ.get("PRINTPIPE_PYINSTALLER", "pyinstaller"),
        help=(
            "PyInstaller command to run. Use "
            "'uvx --from pyinstaller pyinstaller' when pyinstaller is not on PATH."
        ),
    )
    build_windows_standalone.add_argument(
        "--json",
        action="store_true",
        help="Print Windows standalone package output as JSON.",
    )

    build_windows_installer = subparsers.add_parser(
        "build-windows-installer",
        help="Build an Inno Setup Windows installer from a standalone ZIP.",
    )
    build_windows_installer.add_argument(
        "--standalone-zip",
        type=Path,
        required=True,
        help="Prebuilt PrintPipe-Windows-standalone.zip to wrap in the installer.",
    )
    build_windows_installer.add_argument(
        "--output",
        type=Path,
        default=Path("dist/PrintPipeSetup.exe"),
        help="Path for the generated installer executable.",
    )
    build_windows_installer.add_argument(
        "--iscc",
        default=os.environ.get("PRINTPIPE_ISCC", "iscc"),
        help="Inno Setup compiler command.",
    )
    build_windows_installer.add_argument(
        "--signtool",
        default=os.environ.get("PRINTPIPE_SIGNTOOL", "signtool"),
        help="signtool command for Authenticode signing.",
    )
    build_windows_installer.add_argument(
        "--certificate-subject",
        help="Certificate subject passed to signtool /n.",
    )
    build_windows_installer.add_argument(
        "--json",
        action="store_true",
        help="Print Windows installer package output as JSON.",
    )

    build_release = subparsers.add_parser(
        "build-release",
        help="Build current release handoff artifacts plus a checksum manifest.",
    )
    build_release.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/release"),
        help="Directory for generated release artifacts.",
    )
    build_release.add_argument(
        "--adhoc-sign",
        action="store_true",
        help="Ad-hoc sign the embedded macOS app before creating the release DMG.",
    )
    build_release.add_argument(
        "--developer-id-identity",
        help="Developer ID Application identity to sign macOS release artifacts.",
    )
    build_release.add_argument(
        "--notary-profile",
        help="Keychain profile name for notarizing the release DMG with notarytool.",
    )
    build_release.add_argument(
        "--include-standalone",
        action="store_true",
        help="Also build and include a zipped PyInstaller macOS standalone app.",
    )
    build_release.add_argument(
        "--pyinstaller",
        default=os.environ.get("PRINTPIPE_PYINSTALLER", "pyinstaller"),
        help=(
            "PyInstaller command for --include-standalone. Use "
            "'uvx --from pyinstaller pyinstaller' when pyinstaller is not on PATH."
        ),
    )
    build_release.add_argument(
        "--windows-standalone-zip",
        type=Path,
        default=None,
        help="Copy a prebuilt PrintPipe-Windows-standalone.zip into the release bundle.",
    )
    build_release.add_argument(
        "--windows-installer-exe",
        type=Path,
        default=None,
        help="Copy a prebuilt signed PrintPipeSetup.exe into the release bundle.",
    )
    build_release.add_argument(
        "--json",
        action="store_true",
        help="Print release build output as JSON.",
    )

    verify_release = subparsers.add_parser(
        "verify-release",
        help="Verify a release folder against release_manifest.json.",
    )
    verify_release.add_argument(
        "release_dir",
        type=Path,
        help="Release folder containing release_manifest.json.",
    )
    verify_release.add_argument(
        "--json",
        action="store_true",
        help="Print release verification output as JSON.",
    )

    release_status = subparsers.add_parser(
        "release-status",
        help="Summarize release folder integrity plus beta readiness gates.",
    )
    release_status.add_argument(
        "--release-dir",
        type=Path,
        default=Path("dist/release"),
        help="Release folder containing release_manifest.json.",
    )
    release_status.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory where physical evidence run folders are stored.",
    )
    release_status.add_argument(
        "--json",
        action="store_true",
        help="Print the combined release status report as JSON.",
    )
    release_status.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 unless the release and readiness gates are ready.",
    )

    physical = subparsers.add_parser(
        "record-physical-evidence",
        help="Write physical print evidence JSON and Markdown into a run folder.",
    )
    physical.add_argument("run_root", type=Path, help="Run folder to attach evidence to.")
    physical.add_argument("--run-id", help="Override run id; defaults to run folder name.")
    physical.add_argument("--material", required=True, help="Material or filament used.")
    physical.add_argument("--printer", required=True, help="Printer used for the print.")
    physical.add_argument("--object-label", required=True, help="Printed object label.")
    physical.add_argument(
        "--print-type",
        required=True,
        choices=("coupon", "small_object", "slipper", "other"),
        help="Type of physical print being recorded.",
    )
    physical.add_argument(
        "--print-status",
        required=True,
        choices=("not_printed", "passed", "failed", "partial"),
        help="Observed physical print status.",
    )
    physical.add_argument("--operator", default="", help="Person who ran or inspected print.")
    physical.add_argument("--started-at", default="", help="Print start timestamp.")
    physical.add_argument("--completed-at", default="", help="Print completion timestamp.")
    physical.add_argument("--slice-status", default="", help="Manual/GUI slice status.")
    physical.add_argument("--filament-drying", default="", help="Drying settings/time.")
    physical.add_argument("--bed-prep", default="", help="Plate prep and adhesive/release notes.")
    physical.add_argument("--first-layer", default="", help="First-layer observation.")
    physical.add_argument("--adhesion", default="", help="Adhesion observation.")
    physical.add_argument("--warping", default="", help="Warping observation.")
    physical.add_argument("--stringing", default="", help="Stringing observation.")
    physical.add_argument("--layer-bonding", default="", help="Layer bonding observation.")
    physical.add_argument("--flex-recovery", default="", help="Flexible-material recovery note.")
    physical.add_argument("--support-removal", default="", help="Support-removal observation.")
    physical.add_argument(
        "--photo",
        action="append",
        default=[],
        type=Path,
        help="Physical print photo to copy into 90_physical/artifacts; may be repeated.",
    )
    physical.add_argument(
        "--artifact",
        action="append",
        default=[],
        help=(
            "Additional physical artifact as 'label|kind|path|notes'; notes may be omitted "
            "and the artifact is copied into 90_physical/artifacts. May be repeated."
        ),
    )
    physical.add_argument(
        "--note",
        action="append",
        default=[],
        help="Additional physical evidence note; may be repeated.",
    )
    physical.add_argument(
        "--json",
        action="store_true",
        help="Print written evidence paths and missing evidence as JSON.",
    )

    physical_status = subparsers.add_parser(
        "physical-status",
        help="Summarize PLA/PETG/TPU physical validation evidence across run folders.",
    )
    physical_status.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory containing PrintPipe run folders to scan.",
    )
    physical_status.add_argument(
        "--json",
        action="store_true",
        help="Print physical validation status as JSON.",
    )
    physical_status.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 unless all required material families have passed evidence.",
    )

    readiness = subparsers.add_parser(
        "readiness",
        help="Summarize combined beta and release readiness gates.",
    )
    readiness.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory containing PrintPipe run folders to scan for physical evidence.",
    )
    readiness.add_argument(
        "--json",
        action="store_true",
        help="Print the combined readiness report as JSON.",
    )
    readiness.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 unless all readiness gates are ready.",
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
            if args.input is None and args.prompt is None:
                parser.error("run requires an input path or --prompt")
            input_kind = classify_input_path(args.input) if args.input is not None else InputKind.PROMPT
            if args.slice and input_kind != InputKind.MESH:
                parser.error(
                    "--slice currently requires an existing mesh input; "
                    "run prompt/image/GIF/video through meshgen first, then slice the generated bundle"
                )
            if args.input is None:
                result = run_prompt_pipeline(
                    args.prompt,
                    args.runs_dir,
                    material=args.material,
                    printer=args.printer,
                    use_case=args.use_case,
                    prompt_image_provider=args.prompt_image_provider,
                )
            else:
                result = run_existing_mesh_pipeline(
                    args.input,
                    args.runs_dir,
                    material=args.material,
                    printer=args.printer,
                    use_case=args.use_case,
                    run_slice=args.slice,
                    slice_executable=args.bambu_cli,
                    prompt_hint=args.prompt,
                    prompt_image_provider=args.prompt_image_provider,
                )
            layout = result.layout
            report_json = layout.reports_dir / "run_report.json"
            report_markdown = layout.reports_dir / "run_report.md"
            report_html = layout.reports_dir / "run_report.html"
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

    if args.command == "open-folder":
        try:
            result = open_run_folder(args.run_root, target=args.target, dry_run=args.dry_run)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(result.path)
        if args.dry_run:
            print("dry run: not opened")
        return 0

    if args.command == "rebuild-edit":
        if args.bambu_cli is not None and not args.slice:
            parser.error("--bambu-cli requires --slice")
        try:
            result = run_edit_recipe_pipeline(
                args.run_root,
                run_slice=args.slice,
                slice_executable=args.bambu_cli,
            )
        except FileNotFoundError:
            parser.error(f"run root does not exist or is incomplete: {args.run_root}")
        except PipelineError as exc:
            _print_pipeline_error(exc)
            return 2
        except ValueError as exc:
            parser.error(str(exc))
        _print_pipeline_success(result)
        return 0

    if args.command == "serve":
        return _serve(host=args.host, port=args.port, runs_dir=args.runs_dir)

    if args.command == "doctor":
        return _doctor(json_output=args.json, platform_name=args.platform)

    if args.command == "package-smoke":
        return _package_smoke(
            platform_name=args.platform,
            runs_dir=args.runs_dir,
            plan_only=args.plan,
            json_output=args.json,
        )

    if args.command == "build-zipapp":
        return _build_zipapp(output_path=args.output, json_output=args.json)

    if args.command == "build-macos-app":
        _validate_macos_signing_flags(parser, args)
        return _build_macos_app(
            output_path=args.output,
            json_output=args.json,
            adhoc_sign=args.adhoc_sign,
            developer_id_identity=args.developer_id_identity,
        )

    if args.command == "build-macos-standalone":
        return _build_macos_standalone(
            output_path=args.output,
            json_output=args.json,
            pyinstaller_command=args.pyinstaller,
            adhoc_sign=args.adhoc_sign,
        )

    if args.command == "build-macos-dmg":
        _validate_macos_signing_flags(parser, args)
        return _build_macos_dmg(
            output_path=args.output,
            json_output=args.json,
            adhoc_sign=args.adhoc_sign,
            developer_id_identity=args.developer_id_identity,
            notary_profile=args.notary_profile,
        )

    if args.command == "build-windows-portable":
        return _build_windows_portable(output_path=args.output, json_output=args.json)

    if args.command == "build-windows-standalone":
        return _build_windows_standalone(
            output_path=args.output,
            json_output=args.json,
            pyinstaller_command=args.pyinstaller,
        )

    if args.command == "build-windows-installer":
        return _build_windows_installer(
            standalone_zip=args.standalone_zip,
            output_path=args.output,
            json_output=args.json,
            iscc_command=args.iscc,
            signtool_command=args.signtool,
            certificate_subject=args.certificate_subject,
        )

    if args.command == "build-release":
        _validate_macos_signing_flags(parser, args)
        return _build_release(
            output_dir=args.output_dir,
            json_output=args.json,
            adhoc_sign=args.adhoc_sign,
            developer_id_identity=args.developer_id_identity,
            notary_profile=args.notary_profile,
            include_standalone=args.include_standalone,
            pyinstaller_command=args.pyinstaller,
            windows_standalone_zip=args.windows_standalone_zip,
            windows_installer_exe=args.windows_installer_exe,
        )

    if args.command == "verify-release":
        return _verify_release(release_dir=args.release_dir, json_output=args.json)

    if args.command == "release-status":
        return _release_status(
            release_dir=args.release_dir,
            runs_dir=args.runs_dir,
            json_output=args.json,
            strict=args.strict,
        )

    if args.command == "record-physical-evidence":
        try:
            return _record_physical_evidence(args)
        except ValueError as exc:
            parser.error(str(exc))
        except FileNotFoundError:
            parser.error(f"run root does not exist: {args.run_root}")

    if args.command == "physical-status":
        return _physical_status(
            runs_dir=args.runs_dir,
            json_output=args.json,
            strict=args.strict,
        )

    if args.command == "readiness":
        return _readiness(
            runs_dir=args.runs_dir,
            json_output=args.json,
            strict=args.strict,
        )

    parser.print_help()
    return 0


def _serve(*, host: str, port: int, runs_dir: Path) -> int:
    from printpipe.web import server

    server.serve(host=host, port=port, runs_dir=runs_dir)
    return 0


def _validate_macos_signing_flags(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    if getattr(args, "adhoc_sign", False) and getattr(args, "developer_id_identity", None):
        parser.error("--adhoc-sign cannot be combined with --developer-id-identity")
    if getattr(args, "notary_profile", None) and not getattr(args, "developer_id_identity", None):
        parser.error("--notary-profile requires --developer-id-identity")


def _physical_status(*, runs_dir: Path, json_output: bool, strict: bool) -> int:
    from printpipe.beta.physical_status import (
        build_physical_validation_status,
        render_physical_validation_status,
    )

    status = build_physical_validation_status(runs_dir)
    if json_output:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(render_physical_validation_status(status), end="")
    if strict and status["overall_status"] != "passed":
        return 2
    return 0


def _readiness(*, runs_dir: Path, json_output: bool, strict: bool) -> int:
    from printpipe.beta.readiness import (
        build_beta_readiness_report,
        render_beta_readiness_report,
    )

    report = build_beta_readiness_report(runs_dir)
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_beta_readiness_report(report), end="")
    if strict and report["overall_status"] != "ready":
        return 2
    return 0


def _release_status(
    *,
    release_dir: Path,
    runs_dir: Path,
    json_output: bool,
    strict: bool,
) -> int:
    from printpipe.packaging.release_status import (
        build_release_status_report,
        render_release_status_report,
    )

    report = build_release_status_report(release_dir=release_dir, runs_dir=runs_dir)
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_release_status_report(report), end="")
    if strict and report["overall_status"] != "ready":
        return 2
    return 0


def _doctor(*, json_output: bool, platform_name: str | None) -> int:
    from printpipe.env.doctor import build_environment_report, render_environment_report

    report = build_environment_report(platform_name=platform_name)
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_environment_report(report), end="")
    return 0


def _package_smoke(
    *,
    platform_name: str,
    runs_dir: Path | None,
    plan_only: bool,
    json_output: bool,
) -> int:
    resolved_runs_dir = runs_dir or Path(f"runs/package-smoke/{platform_name}")
    if platform_name != "macos":
        if platform_name != "windows":
            raise ValueError(f"unsupported package-smoke platform: {platform_name}")
        from printpipe.packaging.smoke import (
            build_windows_package_smoke_plan,
            run_windows_package_smoke,
        )

        payload = (
            build_windows_package_smoke_plan(runs_dir=resolved_runs_dir).to_dict()
            if plan_only
            else run_windows_package_smoke(runs_dir=resolved_runs_dir).to_dict()
        )
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_render_package_smoke(payload), end="")
        return 0 if payload.get("status", "ok") != "failed" else 2

    from printpipe.packaging.smoke import (
        build_macos_package_smoke_plan,
        run_macos_package_smoke,
    )

    payload = (
        build_macos_package_smoke_plan(runs_dir=resolved_runs_dir).to_dict()
        if plan_only
        else run_macos_package_smoke(runs_dir=resolved_runs_dir).to_dict()
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_package_smoke(payload), end="")
    return 0 if payload.get("status", "ok") != "failed" else 2


def _build_zipapp(*, output_path: Path, json_output: bool) -> int:
    from printpipe.packaging.zipapp import build_zipapp_package

    payload = build_zipapp_package(output_path=output_path)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"zipapp: {payload['artifact_path']}")
        print(f"entrypoint: {payload['entrypoint']}")
        print(f"size bytes: {payload['size_bytes']}")
    return 0


def _build_macos_app(
    *,
    output_path: Path,
    json_output: bool,
    adhoc_sign: bool,
    developer_id_identity: str | None,
) -> int:
    from printpipe.packaging.macos_app import build_macos_app_bundle

    payload = build_macos_app_bundle(
        app_path=output_path,
        adhoc_sign=adhoc_sign,
        developer_id_identity=developer_id_identity,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"macOS app: {payload['app_path']}")
        print(f"executable: {payload['executable_path']}")
        print(f"signed: {str(payload['signed']).lower()}")
        print(f"notarized: {str(payload['notarized']).lower()}")
    return 0


def _build_macos_standalone(
    *,
    output_path: Path,
    json_output: bool,
    pyinstaller_command: str,
    adhoc_sign: bool,
) -> int:
    from printpipe.packaging.macos_standalone import build_macos_standalone_app

    payload = build_macos_standalone_app(
        app_path=output_path,
        pyinstaller_command=pyinstaller_command,
        adhoc_sign=adhoc_sign,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"macOS standalone app: {payload['app_path']}")
        print(f"executable: {payload['executable_path']}")
        print(f"bundles Python runtime: {str(payload['bundles_python_runtime']).lower()}")
        print(f"signed: {str(payload['signed']).lower()}")
        print("notarized: false")
    return 0


def _build_macos_dmg(
    *,
    output_path: Path,
    json_output: bool,
    adhoc_sign: bool,
    developer_id_identity: str | None,
    notary_profile: str | None,
) -> int:
    from printpipe.packaging.macos_dmg import build_macos_dmg_package

    payload = build_macos_dmg_package(
        output_path=output_path,
        adhoc_sign=adhoc_sign,
        developer_id_identity=developer_id_identity,
        notary_profile=notary_profile,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"macOS DMG: {payload['dmg_path']}")
        print(f"app: {payload['app_name']}")
        print(f"drag install: {str(payload['drag_install']).lower()}")
        print(f"signed: {str(payload['signed']).lower()}")
        print(f"notarized: {str(payload['notarized']).lower()}")
    return 0


def _build_windows_portable(*, output_path: Path, json_output: bool) -> int:
    from printpipe.packaging.windows_portable import build_windows_portable_package

    payload = build_windows_portable_package(output_path=output_path)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Windows portable ZIP: {payload['archive_path']}")
        print(f"zipapp: {payload['zipapp_path']}")
        print(f"cmd launcher: {payload['cmd_launcher']}")
        print(f"PowerShell launcher: {payload['powershell_launcher']}")
        print("signed: false")
    return 0


def _build_windows_standalone(
    *,
    output_path: Path,
    json_output: bool,
    pyinstaller_command: str,
) -> int:
    from printpipe.packaging.windows_standalone import build_windows_standalone_package

    payload = build_windows_standalone_package(
        output_path=output_path,
        pyinstaller_command=pyinstaller_command,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Windows standalone ZIP: {payload['archive_path']}")
        print(f"executable: {payload['executable_path']}")
        print(f"bundles Python runtime: {str(payload['bundles_python_runtime']).lower()}")
        print("signed: false")
    return 0


def _build_windows_installer(
    *,
    standalone_zip: Path,
    output_path: Path,
    json_output: bool,
    iscc_command: str,
    signtool_command: str,
    certificate_subject: str | None,
) -> int:
    from printpipe.packaging.windows_installer import build_windows_installer_package

    payload = build_windows_installer_package(
        standalone_zip=standalone_zip,
        output_path=output_path,
        iscc_command=iscc_command,
        signtool_command=signtool_command,
        certificate_subject=certificate_subject,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Windows installer: {payload['installer_path']}")
        print(f"kind: {payload['installer_kind']}")
        print(f"signed: {str(payload['signed']).lower()}")
    return 0


def _build_release(
    *,
    output_dir: Path,
    json_output: bool,
    adhoc_sign: bool,
    developer_id_identity: str | None,
    notary_profile: str | None,
    include_standalone: bool,
    pyinstaller_command: str,
    windows_standalone_zip: Path | None,
    windows_installer_exe: Path | None,
) -> int:
    from printpipe.packaging.release import build_release_bundle

    payload = build_release_bundle(
        output_dir=output_dir,
        adhoc_sign=adhoc_sign,
        developer_id_identity=developer_id_identity,
        notary_profile=notary_profile,
        include_standalone=include_standalone,
        pyinstaller_command=pyinstaller_command,
        windows_standalone_zip=windows_standalone_zip,
        windows_installer_exe=windows_installer_exe,
    )
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"release dir: {payload['output_dir']}")
        print(f"manifest: {payload['manifest_path']}")
        print(f"artifacts: {payload['artifact_count']}")
    return 0


def _verify_release(*, release_dir: Path, json_output: bool) -> int:
    from printpipe.packaging.release import verify_release_bundle

    payload = verify_release_bundle(release_dir)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"release dir: {payload['release_dir']}")
        print(f"manifest: {payload['manifest_path']}")
        print(f"status: {payload['status']}")
        print(f"checks: {len(payload['checks'])}")
        if payload["failures"]:
            print("failures:")
            for failure in payload["failures"]:
                print(f"- {failure['id']}: {failure['message']}")
    return 0 if payload["status"] == "ok" else 2


def _render_package_smoke(payload: dict[str, Any]) -> str:
    lines = [
        f"platform: {payload.get('platform', 'unknown')}",
        f"runs dir: {payload.get('runs_dir', 'unknown')}",
    ]
    if "status" in payload:
        lines.append(f"status: {payload['status']}")
    if payload.get("run_root"):
        lines.append(f"run root: {payload['run_root']}")
    checks = payload.get("checks")
    if isinstance(checks, list):
        lines.append("checks:")
        for check in checks:
            if isinstance(check, dict):
                lines.append(
                    f"- {check.get('id', 'unknown')}: {check.get('status', 'unknown')}"
                )
    steps = payload.get("steps")
    if isinstance(steps, list):
        lines.append("steps:")
        for step in steps:
            if isinstance(step, dict):
                lines.append(
                    f"- {step.get('id', 'unknown')}: {step.get('command', '')}"
                )
    return "\n".join(lines) + "\n"


def _record_physical_evidence(args: argparse.Namespace) -> int:
    from printpipe.beta.physical import (
        PhysicalArtifact,
        build_physical_print_evidence,
        write_physical_evidence_files,
    )

    run_root = args.run_root.expanduser().resolve()
    if not run_root.exists():
        raise FileNotFoundError(run_root)
    artifacts: list[PhysicalArtifact] = [
        PhysicalArtifact(
            label=f"Physical print photo {index}",
            path=photo,
            kind="photo",
        )
        for index, photo in enumerate(args.photo, start=1)
    ]
    artifacts.extend(_parse_physical_artifact(value) for value in args.artifact)
    evidence = build_physical_print_evidence(
        run_id=args.run_id or run_root.name,
        material=args.material,
        printer=args.printer,
        object_label=args.object_label,
        print_type=args.print_type,
        print_status=args.print_status,
        operator=args.operator,
        started_at=args.started_at,
        completed_at=args.completed_at,
        slice_status=args.slice_status,
        filament_drying=args.filament_drying,
        bed_prep=args.bed_prep,
        first_layer=args.first_layer,
        adhesion=args.adhesion,
        warping=args.warping,
        stringing=args.stringing,
        layer_bonding=args.layer_bonding,
        flex_recovery=args.flex_recovery,
        support_removal=args.support_removal,
        artifacts=tuple(artifacts),
        notes=tuple(args.note),
    )
    try:
        result = write_physical_evidence_files(
            run_root=run_root,
            evidence=evidence,
            copy_artifacts=True,
        )
    except FileNotFoundError:
        raise FileNotFoundError(run_root)
    result.update(_refresh_reports_with_physical_evidence(run_root, result))

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"physical evidence json: {result['json_path']}")
        print(f"physical evidence markdown: {result['markdown_path']}")
        missing = result["missing_required_evidence"]
        if missing:
            print("missing required evidence: " + ", ".join(missing))
        else:
            print("missing required evidence: none")
    return 0


def _refresh_reports_with_physical_evidence(
    run_root: Path,
    evidence_result: dict[str, Any],
) -> dict[str, str]:
    from printpipe.reports import write_run_report_dict
    from printpipe.reports.html import write_html_report

    try:
        layout = load_run(run_root)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {}
    report_json = layout.reports_dir / "run_report.json"
    if not report_json.exists():
        return {}

    evidence_json = Path(str(evidence_result["json_path"]))
    evidence_payload = json.loads(evidence_json.read_text(encoding="utf-8"))
    evidence_payload["missing_required_evidence"] = list(
        evidence_result.get("missing_required_evidence", [])
    )
    evidence_payload["packet_paths"] = {
        "json": "90_physical/physical_evidence.json",
        "markdown": "90_physical/physical_evidence.md",
    }

    report_payload = json.loads(report_json.read_text(encoding="utf-8"))
    report_payload["physical_evidence"] = evidence_payload
    write_run_report_dict(layout, report_payload)
    write_html_report(layout, report_payload)
    return {
        "report_json_path": str(layout.reports_dir / "run_report.json"),
        "report_markdown_path": str(layout.reports_dir / "run_report.md"),
        "report_html_path": str(layout.reports_dir / "run_report.html"),
    }


def _parse_physical_artifact(value: str) -> Any:
    from printpipe.beta.physical import PhysicalArtifact

    parts = value.split("|", 3)
    if len(parts) < 3:
        raise ValueError(
            "--artifact must use 'label|kind|path|notes' with notes optional"
        )
    label, kind, path = (part.strip() for part in parts[:3])
    notes = parts[3].strip() if len(parts) == 4 else ""
    if not label or not kind or not path:
        raise ValueError("--artifact label, kind, and path are required")
    return PhysicalArtifact(label=label, path=Path(path), kind=kind, notes=notes)


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


def _print_pipeline_success(result: Any) -> None:
    layout = result.layout
    print(f"run id: {layout.run_id}")
    print(f"run root: {layout.root}")
    print(f"input: {layout.original_input}")
    print(f"report json: {layout.reports_dir / 'run_report.json'}")
    print(f"report markdown: {layout.reports_dir / 'run_report.md'}")
    print(f"report html: {layout.reports_dir / 'run_report.html'}")


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
