"""TRELLIS.2 runner for the printpipe media meshgen command contract.

Configure it as the TRELLIS.2 provider command, for example::

    export PRINTPIPE_TRELLIS2_COMMAND="python -m printpipe.meshgen.trellis2 \\
        --remote gpu-host --remote-shell 'wsl -d Ubuntu -- bash -s'"

printpipe appends ``--input-kind``, ``--output``, ``--output-format``,
``--source`` and the other provider arguments.

Without ``--remote`` the worker runs on this machine and needs CUDA, torch and
TRELLIS.2 importable from ``--python``. With ``--remote HOST`` the reference
image and the worker script are streamed over ssh to the GPU machine, inference
runs there, and the mesh is streamed back. The runner never writes ``--output``
unless TRELLIS.2 produced a mesh that passes a format check.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Sequence


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MODEL_UNAVAILABLE = 3
EXIT_INFERENCE_FAILED = 4
EXIT_OUTPUT_MISSING = 5
EXIT_REMOTE_FAILED = 6

OUTPUT_FORMATS = ("glb", "stl", "obj")
DEFAULT_MODEL = "microsoft/TRELLIS.2-4B"
WORKER_PATH = Path(__file__).with_name("trellis2_worker.py")
RESULT_BEGIN = "__PRINTPIPE_TRELLIS2_RESULT_BEGIN__"
RESULT_END = "__PRINTPIPE_TRELLIS2_RESULT_END__"
QUALITY_PIPELINE_TYPES = {
    "draft": "512",
    "standard": "1024_cascade",
    "high": "1536_cascade",
}


def pipeline_type_for_quality(quality: str) -> str:
    return QUALITY_PIPELINE_TYPES.get(quality, QUALITY_PIPELINE_TYPES["standard"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m printpipe.meshgen.trellis2",
        description="Run TRELLIS.2 image-to-3D locally (CUDA) or on a remote GPU host over ssh.",
    )
    contract = parser.add_argument_group("printpipe provider arguments")
    contract.add_argument("--input-kind", default="image")
    contract.add_argument("--output", required=True, type=Path)
    contract.add_argument("--output-format", choices=OUTPUT_FORMATS)
    contract.add_argument("--target-use", default="")
    contract.add_argument("--quality", default="standard")
    contract.add_argument("--source", action="append", default=[], type=Path)
    contract.add_argument("--reference-image", action="append", default=[], type=Path)
    contract.add_argument("--prompt")
    contract.add_argument("--seed", type=int, default=42)
    contract.add_argument("--params-json")

    model = parser.add_argument_group("TRELLIS.2 options")
    model.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face id or local model dir.")
    model.add_argument("--pipeline-type", choices=("512", "1024", "1024_cascade", "1536_cascade"))
    model.add_argument("--texture-size", type=int, default=1024)
    model.add_argument("--decimation-target", type=int, default=500000)
    model.add_argument(
        "--rembg-model",
        help="Override the background-removal model (for example ZhengPeng7/BiRefNet).",
    )
    model.add_argument("--gpu", default="0", help="CUDA_VISIBLE_DEVICES for the worker.")
    model.add_argument("--trellis-root", default="~/printpipe-trellis2/TRELLIS.2")

    local = parser.add_argument_group("local mode")
    local.add_argument("--python", default=sys.executable, help="Python of the TRELLIS.2 env.")

    remote = parser.add_argument_group("remote mode")
    remote.add_argument("--remote", help="ssh host of the GPU machine.")
    remote.add_argument("--ssh", default="ssh")
    remote.add_argument("--ssh-option", action="append", default=[])
    remote.add_argument(
        "--remote-shell",
        default="bash -s",
        help="Command on the host that reads a bash script from stdin.",
    )
    remote.add_argument("--conda-sh", default="~/miniconda3/etc/profile.d/conda.sh")
    remote.add_argument("--conda-env", default="trellis2")
    remote.add_argument("--remote-python", default="python")
    remote.add_argument("--work-dir", default="~/printpipe-trellis2/jobs")
    remote.add_argument("--timeout", type=int, default=1750, help="Seconds before ssh is stopped.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = list(dict.fromkeys([*args.source, *args.reference_image]))
    if not sources:
        return _fail(EXIT_USAGE, "at least one --source image is required.")
    missing = [path for path in sources if not path.is_file()]
    if missing:
        return _fail(EXIT_USAGE, f"source image does not exist: {missing[0]}")
    output_format = args.output_format or args.output.suffix.lower().lstrip(".")
    if output_format not in OUTPUT_FORMATS:
        return _fail(EXIT_USAGE, f"unsupported output format: {output_format or args.output}")
    if args.prompt:
        _log("TRELLIS.2 is image-to-3D only; the prompt hint is not used.")
    if len(sources) > 1:
        _log(f"TRELLIS.2 takes one image; using {sources[0].name} of {len(sources)} references.")
    pipeline_type = args.pipeline_type or pipeline_type_for_quality(args.quality)

    with tempfile.TemporaryDirectory(prefix="printpipe-trellis2-") as staging_name:
        staging = Path(staging_name)
        if args.remote:
            code, result, staged_mesh = _run_remote(
                args, sources[0], output_format, pipeline_type, staging
            )
        else:
            code, result, staged_mesh = _run_local(
                args, sources[0], output_format, pipeline_type, staging
            )
        if code != EXIT_OK:
            return _fail(code, str(result.get("error") or "TRELLIS.2 did not succeed."))
        if staged_mesh is None or not _looks_like_mesh(staged_mesh, output_format):
            return _fail(
                EXIT_OUTPUT_MISSING,
                f"TRELLIS.2 reported success but returned no usable mesh ({output_format}).",
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged_mesh, args.output)

    print(
        json.dumps(
            {
                "output_path": str(args.output),
                "mode": "remote" if args.remote else "local",
                "remote_host": args.remote,
                "model_id": args.model,
                "pipeline_type": pipeline_type,
                "worker_result": result,
            },
            sort_keys=True,
        )
    )
    return EXIT_OK


def _worker_args(
    args: argparse.Namespace,
    *,
    image: str,
    output: str,
    result: str,
    output_format: str,
    pipeline_type: str,
    model: str,
) -> list[str]:
    worker_args = [
        "--input",
        image,
        "--output",
        output,
        "--output-format",
        output_format,
        "--result",
        result,
        "--model",
        model,
        "--pipeline-type",
        pipeline_type,
        "--seed",
        str(args.seed),
        "--texture-size",
        str(args.texture_size),
        "--decimation-target",
        str(args.decimation_target),
    ]
    if args.rembg_model:
        worker_args.extend(("--rembg-model", args.rembg_model))
    return worker_args


def _run_local(
    args: argparse.Namespace,
    image: Path,
    output_format: str,
    pipeline_type: str,
    staging: Path,
) -> tuple[int, dict[str, Any], Path | None]:
    staged_mesh = staging / f"mesh.{output_format}"
    result_path = staging / "result.json"
    model = str(Path(args.model).expanduser()) if args.model.startswith("~") else args.model
    command = [
        args.python,
        str(WORKER_PATH),
        *_worker_args(
            args,
            image=str(image),
            output=str(staged_mesh),
            result=str(result_path),
            output_format=output_format,
            pipeline_type=pipeline_type,
            model=model,
        ),
    ]
    env = os.environ.copy()
    trellis_root = str(Path(args.trellis_root).expanduser())
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (trellis_root, env.get("PYTHONPATH"))))
    env["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    except OSError as exc:
        return EXIT_MODEL_UNAVAILABLE, {"error": f"cannot start {args.python}: {exc}"}, None
    _forward(completed.stderr)
    result = _read_result(result_path)
    code = completed.returncode
    if code != EXIT_OK:
        result.setdefault("error", _tail(completed.stderr) or f"worker exited with {code}")
        return code, result, None
    return code, result, staged_mesh if staged_mesh.exists() else None


def _run_remote(
    args: argparse.Namespace,
    image: Path,
    output_format: str,
    pipeline_type: str,
    staging: Path,
) -> tuple[int, dict[str, Any], Path | None]:
    image_name = f"input{image.suffix.lower() or '.png'}"
    script = build_remote_script(args, image_name, output_format, pipeline_type)
    payload = base64.b64encode(_input_tarball(image, image_name))
    stdin = script.encode("utf-8") + payload + b"\n"
    command = [
        args.ssh,
        "-o",
        "BatchMode=yes",
        *[part for option in args.ssh_option for part in ("-o", option)],
        args.remote,
        *shlex.split(args.remote_shell),
    ]
    try:
        completed = subprocess.run(
            command, input=stdin, capture_output=True, timeout=args.timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return EXIT_REMOTE_FAILED, {"error": f"remote TRELLIS.2 job timed out after {args.timeout}s"}, None
    except OSError as exc:
        return EXIT_REMOTE_FAILED, {"error": f"cannot start {args.ssh}: {exc}"}, None
    stderr = completed.stderr.decode("utf-8", errors="replace")
    _forward(stderr)
    archive = _extract_result_archive(completed.stdout.decode("utf-8", errors="replace"))
    if archive is None:
        detail = _tail(stderr) or f"ssh exited with {completed.returncode}"
        return EXIT_REMOTE_FAILED, {"error": f"remote TRELLIS.2 job on {args.remote} failed: {detail}"}, None
    _safe_extract(archive, staging)
    result = _read_result(staging / "result.json")
    code = completed.returncode
    if code != EXIT_OK:
        result.setdefault("error", _tail(stderr) or f"remote worker exited with {code}")
        return code, result, None
    staged_mesh = staging / f"mesh.{output_format}"
    return code, result, staged_mesh if staged_mesh.exists() else None


def build_remote_script(
    args: argparse.Namespace,
    image_name: str,
    output_format: str,
    pipeline_type: str,
) -> str:
    """Bash job read from stdin; the base64 input tarball follows the closing brace.

    bash reads a piped script one byte at a time and parses the whole ``{ ... }``
    group before running it, so ``base64 -d`` inside the group consumes exactly
    the payload that follows.
    """

    worker_args = _worker_args(
        args,
        image=f"$JOB/in/{image_name}",
        output=f"$JOB/out/mesh.{output_format}",
        result="$JOB/out/result.json",
        output_format=output_format,
        pipeline_type=pipeline_type,
        model=args.model,
    )
    quoted_worker_args = " ".join(_remote_word(arg) for arg in worker_args)
    conda_sh = _remote_path(args.conda_sh)
    lines = [
        "{",
        f"WORK={_remote_path(args.work_dir)}",
        'mkdir -p "$WORK" || exit 6',
        'JOB=$(mktemp -d "$WORK/job-XXXXXX") || exit 6',
        'mkdir -p "$JOB/in" "$JOB/out" || exit 6',
        'base64 -d > "$JOB/in.tar.gz" || exit 6',
        'tar -xzf "$JOB/in.tar.gz" -C "$JOB/in" || exit 6',
        "status=0",
        f"if [ -f {conda_sh} ]; then",
        f"  . {conda_sh} && conda activate {shlex.quote(args.conda_env)} || status=3",
        "else",
        f"  echo \"TRELLIS.2 runner: conda.sh not found at \"{conda_sh} >&2; status=3",
        "fi",
        'if [ "$status" -eq 0 ]; then',
        f"  export PYTHONPATH={_remote_path(args.trellis_root)}\"${{PYTHONPATH:+:$PYTHONPATH}}\"",
        f"  export CUDA_VISIBLE_DEVICES={shlex.quote(str(args.gpu))}",
        "  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        f"  {_remote_word(args.remote_python)} \"$JOB/in/trellis2_worker.py\" {quoted_worker_args} 1>&2"
        " || status=$?",
        "fi",
        'echo "TRELLIS.2 runner: remote job dir $JOB" >&2',
        f"echo {RESULT_BEGIN}",
        'tar -czf - -C "$JOB/out" . | base64',
        f"echo {RESULT_END}",
        'exit "$status"',
        "}",
    ]
    return "\n".join(lines) + "\n"


def _remote_path(value: str) -> str:
    if value == "~":
        return '"$HOME"'
    if value.startswith("~/"):
        return '"$HOME"/' + shlex.quote(value[2:])
    return shlex.quote(value)


def _remote_word(value: str) -> str:
    if value.startswith("$JOB/"):
        return '"$JOB"/' + shlex.quote(value[len("$JOB/") :])
    return _remote_path(value)


def _input_tarball(image: Path, image_name: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(image, arcname=image_name)
        archive.add(WORKER_PATH, arcname="trellis2_worker.py")
    return buffer.getvalue()


def _extract_result_archive(stdout: str) -> bytes | None:
    lines = [line.strip() for line in stdout.splitlines()]
    if RESULT_BEGIN not in lines or RESULT_END not in lines:
        return None
    begin = lines.index(RESULT_BEGIN)
    end = lines.index(RESULT_END, begin)
    try:
        return base64.b64decode("".join(lines[begin + 1 : end]))
    except ValueError:
        return None


def _safe_extract(archive: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(extracted.read())


def _looks_like_mesh(path: Path, output_format: str) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    data = path.read_bytes()
    if output_format == "glb":
        return len(data) >= 12 and data[:4] == b"glTF"
    if output_format == "stl":
        if data.lstrip()[:5].lower() == b"solid" and b"facet" in data:
            return True
        if len(data) >= 84:
            triangles = int.from_bytes(data[80:84], "little")
            return triangles > 0 and len(data) == 84 + 50 * triangles
        return False
    if output_format == "obj":
        text = data.decode("utf-8", errors="ignore")
        return any(line.startswith("v ") for line in text.splitlines()) and any(
            line.startswith("f ") for line in text.splitlines()
        )
    return False


def _read_result(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _forward(text: str) -> None:
    if text:
        sys.stderr.write(text if text.endswith("\n") else text + "\n")


def _log(message: str) -> None:
    sys.stderr.write(f"TRELLIS.2 runner: {message}\n")


def _fail(code: int, message: str) -> int:
    _log(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
