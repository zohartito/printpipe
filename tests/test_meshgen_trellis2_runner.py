"""TRELLIS.2 runner: local CUDA mode and remote (ssh) mode never fabricate a mesh."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from printpipe.meshgen import trellis2


FIXTURE_STL = (
    Path(__file__).parent
    / "fixtures"
    / "objects"
    / "existing_stl_pipeline"
    / "tiny_tetrahedron.stl"
)
needs_posix_shell = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("tar") is None or shutil.which("base64") is None,
    reason="remote-mode test runs the job script with local bash, tar and base64",
)


def _write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)
    return path


def _fake_ssh(tmp_path: Path) -> Path:
    """Stand-in for ssh: records the host, then runs the remote command locally."""

    return _write_script(
        tmp_path / "fake_ssh.py",
        "import subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "while args and args[0] == '-o':\n"
        "    args = args[2:]\n"
        "host, command = args[0], args[1:]\n"
        f"open({str(tmp_path / 'ssh_host.txt')!r}, 'w').write(host)\n"
        "sys.exit(subprocess.run(' '.join(command), shell=True).returncode)\n",
    )


def _fake_conda_sh(tmp_path: Path) -> Path:
    path = tmp_path / "conda.sh"
    path.write_text("conda() { :; }\n", encoding="utf-8")
    return path


def _remote_args(tmp_path: Path, remote_python: Path, *, output: Path) -> list[str]:
    source = tmp_path / "reference.png"
    source.write_bytes(b"\x89PNG fake reference")
    return [
        "--remote",
        "desktop-zt",
        "--ssh",
        str(_fake_ssh(tmp_path)),
        "--remote-shell",
        "bash -s",
        "--conda-sh",
        str(_fake_conda_sh(tmp_path)),
        "--remote-python",
        str(remote_python),
        "--work-dir",
        str(tmp_path / "remote-jobs"),
        "--trellis-root",
        str(tmp_path / "TRELLIS.2"),
        "--input-kind",
        "image",
        "--output",
        str(output),
        "--output-format",
        output.suffix.lstrip("."),
        "--source",
        str(source),
        "--seed",
        "11",
    ]


@needs_posix_shell
def test_remote_mode_uploads_image_runs_worker_and_returns_mesh(tmp_path: Path, capsys):
    fake_python = _write_script(
        tmp_path / "fake_trellis_python.py",
        "import argparse, json, shutil, sys\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('worker')\n"
        "parser.add_argument('--input', required=True)\n"
        "parser.add_argument('--output', required=True)\n"
        "parser.add_argument('--result', required=True)\n"
        "args, _ = parser.parse_known_args()\n"
        "assert Path(args.worker).name == 'trellis2_worker.py', args.worker\n"
        "assert Path(args.input).read_bytes() == b'\\x89PNG fake reference'\n"
        f"shutil.copyfile({str(FIXTURE_STL)!r}, args.output)\n"
        "Path(args.result).write_text(json.dumps({'status': 'succeeded', "
        "'peak_gpu_memory_reserved_mb': 1234.0}))\n",
    )
    output = tmp_path / "printpipe-run" / "trellis2.stl"
    output.parent.mkdir()

    exit_code = trellis2.main(_remote_args(tmp_path, fake_python, output=output))

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert output.read_bytes() == FIXTURE_STL.read_bytes()
    assert (tmp_path / "ssh_host.txt").read_text() == "desktop-zt"
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["output_path"] == str(output)
    assert payload["mode"] == "remote"
    assert payload["worker_result"]["peak_gpu_memory_reserved_mb"] == 1234.0
    job_dirs = list((tmp_path / "remote-jobs").iterdir())
    assert len(job_dirs) == 1
    assert (job_dirs[0] / "in" / "trellis2_worker.py").exists()


@needs_posix_shell
def test_remote_worker_failure_is_reported_and_no_mesh_is_written(tmp_path: Path, capsys):
    fake_python = _write_script(
        tmp_path / "fake_trellis_python.py",
        "import argparse, json, sys\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('worker')\n"
        "parser.add_argument('--result', required=True)\n"
        "args, _ = parser.parse_known_args()\n"
        "message = 'TRELLIS.2 model unavailable: gated Hugging Face dependency'\n"
        "Path(args.result).write_text(json.dumps({'status': 'failed', 'error': message}))\n"
        "sys.stderr.write(message + '\\n')\n"
        "sys.exit(3)\n",
    )
    output = tmp_path / "trellis2.stl"

    exit_code = trellis2.main(_remote_args(tmp_path, fake_python, output=output))

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "gated Hugging Face dependency" in captured.err
    assert not output.exists()


@needs_posix_shell
def test_remote_success_without_mesh_is_an_error(tmp_path: Path, capsys):
    fake_python = _write_script(
        tmp_path / "fake_trellis_python.py",
        "import argparse\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('worker')\n"
        "parser.add_argument('--output', required=True)\n"
        "args, _ = parser.parse_known_args()\n"
        "Path(args.output).write_bytes(b'')\n",
    )
    output = tmp_path / "trellis2.stl"

    exit_code = trellis2.main(_remote_args(tmp_path, fake_python, output=output))

    captured = capsys.readouterr()
    assert exit_code == trellis2.EXIT_OUTPUT_MISSING
    assert "no usable mesh" in captured.err
    assert not output.exists()


def test_remote_transport_failure_is_reported(tmp_path: Path, capsys):
    broken_ssh = _write_script(
        tmp_path / "broken_ssh.py",
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        "sys.stderr.write('ssh: connect to host desktop-zt port 22: Connection refused\\n')\n"
        "sys.exit(255)\n",
    )
    source = tmp_path / "reference.png"
    source.write_bytes(b"png")
    output = tmp_path / "trellis2.glb"

    exit_code = trellis2.main(
        [
            "--remote",
            "desktop-zt",
            "--ssh",
            str(broken_ssh),
            "--output",
            str(output),
            "--source",
            str(source),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == trellis2.EXIT_REMOTE_FAILED
    assert "Connection refused" in captured.err
    assert not output.exists()


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is not None,
    reason="checks the no-CUDA path on a machine without torch",
)
def test_local_mode_without_torch_fails_clearly(tmp_path: Path, capsys):
    source = tmp_path / "reference.png"
    source.write_bytes(b"png")
    output = tmp_path / "trellis2.glb"

    exit_code = trellis2.main(
        [
            "--python",
            sys.executable,
            "--trellis-root",
            str(tmp_path / "TRELLIS.2"),
            "--output",
            str(output),
            "--source",
            str(source),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == trellis2.EXIT_MODEL_UNAVAILABLE
    assert "torch" in captured.err
    assert "--remote" in captured.err
    assert not output.exists()


def test_missing_source_is_a_usage_error(tmp_path: Path, capsys):
    exit_code = trellis2.main(
        ["--output", str(tmp_path / "out.glb"), "--source", str(tmp_path / "missing.png")]
    )

    assert exit_code == trellis2.EXIT_USAGE
    assert "does not exist" in capsys.readouterr().err


@needs_posix_shell
def test_same_path_as_source_and_reference_counts_once(tmp_path: Path, capsys):
    fake_python = _write_script(
        tmp_path / "fake_trellis_python.py",
        "import argparse, shutil\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('worker')\n"
        "parser.add_argument('--output', required=True)\n"
        "args, _ = parser.parse_known_args()\n"
        f"shutil.copyfile({str(FIXTURE_STL)!r}, args.output)\n",
    )
    output = tmp_path / "trellis2.stl"
    argv = _remote_args(tmp_path, fake_python, output=output)
    argv += ["--reference-image", argv[argv.index("--source") + 1]]

    exit_code = trellis2.main(argv)

    assert exit_code == 0
    assert "takes one image" not in capsys.readouterr().err


def test_gated_dependency_error_names_the_repo():
    from printpipe.meshgen.trellis2_worker import _load_error_message

    message = _load_error_message(
        "~/models/TRELLIS.2-4B",
        OSError(
            "You are trying to access a gated repo.\n"
            "Make sure to have access to it at "
            "https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m.\n"
            "401 Client Error."
        ),
    )

    assert "https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m" in message
    assert "hf auth login" in message


def test_quality_maps_to_pipeline_type():
    assert trellis2.pipeline_type_for_quality("draft") == "512"
    assert trellis2.pipeline_type_for_quality("standard") == "1024_cascade"
    assert trellis2.pipeline_type_for_quality("high") == "1536_cascade"
    assert trellis2.pipeline_type_for_quality("unknown") == "1024_cascade"
