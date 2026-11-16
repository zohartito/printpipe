"""TRELLIS.2 inference worker for printpipe.

Runs inside the TRELLIS.2 Python environment on a CUDA machine. It is a
standalone script (no printpipe imports) because the runner copies it to the
GPU host for remote jobs. It writes the mesh only after TRELLIS.2 returns one,
and always writes a JSON result with timings, peak GPU memory or the error.

Exit codes: 0 ok, 3 model unavailable, 4 inference failed, 5 no usable mesh.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

EXIT_MODEL_UNAVAILABLE = 3
EXIT_INFERENCE_FAILED = 4
EXIT_OUTPUT_MISSING = 5
GATED_DEPENDENCIES = (
    "facebook/dinov3-vitl16-pretrain-lvd1689m (Meta DINOv3 licence, manual approval)",
    "briaai/RMBG-2.0 (Bria RMBG-2.0 licence, non-commercial)",
)


class WorkerError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _positive_finite_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive finite number") from exc
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def _scale_vertices(vertices, target_size_mm: float) -> tuple:
    """Return scaled vertices, factor and bbox size without mutating the input array."""
    if len(vertices) == 0:
        raise WorkerError(EXIT_OUTPUT_MISSING, "no usable mesh: vertices are empty")
    bbox_size = [float(size) for size in vertices.max(axis=0) - vertices.min(axis=0)]
    longest = max(bbox_size)
    if any(not 0 <= size < float("inf") for size in bbox_size) or longest == 0:
        raise WorkerError(
            EXIT_OUTPUT_MISSING, "no usable mesh: bounding box is zero or non-finite"
        )
    scale_factor = target_size_mm / longest
    if not 0 < scale_factor < float("inf"):
        raise WorkerError(EXIT_OUTPUT_MISSING, "no usable mesh: scale factor is not representable")
    scaled_vertices = vertices * scale_factor
    if not (abs(scaled_vertices) < float("inf")).all():
        raise WorkerError(EXIT_OUTPUT_MISSING, "no usable mesh: scaled vertices are non-finite")
    return scaled_vertices, scale_factor, [size * scale_factor for size in bbox_size]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRELLIS.2 image-to-3D worker for printpipe.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--output-format", choices=("glb", "stl", "obj"), default="glb")
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--model", default="microsoft/TRELLIS.2-4B")
    parser.add_argument("--pipeline-type", default="1024_cascade")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--decimation-target", type=int, default=500000)
    parser.add_argument(
        "--target-size-mm", type=_positive_finite_float, default=80.0,
        help="Scale uniformly about the origin to this longest bbox dimension in mm (default: 80).",
    )
    parser.add_argument("--rembg-model")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: dict = {
        "schema_version": 1,
        "status": "failed",
        "model": args.model,
        "pipeline_type": args.pipeline_type,
        "seed": args.seed,
        "output_format": args.output_format,
    }
    started = time.perf_counter()
    code = 0
    try:
        _generate(args, result)
        result["status"] = "succeeded"
    except WorkerError as exc:
        code = exc.code
        result["error"] = exc.message
        sys.stderr.write(f"TRELLIS.2 worker: {exc.message}\n")
    result["wall_seconds"] = round(time.perf_counter() - started, 2)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return code


def _generate(args: argparse.Namespace, result: dict) -> None:
    try:
        import torch
    except Exception as exc:  # ImportError or a broken CUDA install
        raise WorkerError(
            EXIT_MODEL_UNAVAILABLE,
            f"torch is not importable in {sys.executable} ({exc}). TRELLIS.2 needs its own "
            "CUDA environment; run on the GPU machine or pass --remote HOST to the "
            "printpipe TRELLIS.2 runner.",
        ) from exc
    if not torch.cuda.is_available():
        raise WorkerError(
            EXIT_MODEL_UNAVAILABLE,
            "CUDA is not available to torch here; TRELLIS.2 needs an NVIDIA GPU with at "
            "least 24 GB. Pass --remote HOST to the printpipe TRELLIS.2 runner.",
        )
    try:
        from PIL import Image
        import o_voxel
        import trimesh
        from trellis2.pipelines import Trellis2ImageTo3DPipeline
    except Exception as exc:
        raise WorkerError(
            EXIT_MODEL_UNAVAILABLE,
            f"TRELLIS.2 is not importable ({type(exc).__name__}: {exc}); point --trellis-root "
            "at a TRELLIS.2 checkout and use the environment its setup.sh built.",
        ) from exc
    if args.rembg_model:
        _override_rembg_model(args.rembg_model)

    result["device"] = torch.cuda.get_device_name(0)
    load_started = time.perf_counter()
    try:
        pipeline = Trellis2ImageTo3DPipeline.from_pretrained(args.model)
        pipeline.cuda()
    except Exception as exc:
        raise WorkerError(EXIT_MODEL_UNAVAILABLE, _load_error_message(args.model, exc)) from exc
    result["load_seconds"] = round(time.perf_counter() - load_started, 2)

    torch.cuda.reset_peak_memory_stats()
    try:
        image = Image.open(args.input)
        image.load()
        inference_started = time.perf_counter()
        mesh = pipeline.run(image, seed=args.seed, pipeline_type=args.pipeline_type)[0]
        mesh.simplify(16777216)  # nvdiffrast limit, as in TRELLIS.2 example.py
        result["inference_seconds"] = round(time.perf_counter() - inference_started, 2)
        export_started = time.perf_counter()
        textured = o_voxel.postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=mesh.layout,
            voxel_size=mesh.voxel_size,
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=args.decimation_target,
            texture_size=args.texture_size,
            remesh=True,
            remesh_band=1,
            remesh_project=0,
            verbose=False,
        )
        result["export_seconds"] = round(time.perf_counter() - export_started, 2)
    except torch.cuda.OutOfMemoryError as exc:
        raise WorkerError(EXIT_INFERENCE_FAILED, f"CUDA out of memory: {exc}") from exc
    except Exception as exc:
        raise WorkerError(
            EXIT_INFERENCE_FAILED, f"TRELLIS.2 inference failed: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        result["peak_gpu_memory_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        result["peak_gpu_memory_reserved_mb"] = round(torch.cuda.max_memory_reserved() / 2**20, 1)

    vertices, scale_factor, bbox_size_mm = _scale_vertices(textured.vertices, args.target_size_mm)
    textured.vertices = vertices
    result["scale_factor"] = scale_factor
    result["bbox_size_mm"] = bbox_size_mm
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output_format == "glb":
        textured.export(args.output)
    else:
        geometry = trimesh.Trimesh(vertices=textured.vertices, faces=textured.faces, process=False)
        geometry.export(args.output, file_type=args.output_format)
    result["vertex_count"] = int(len(textured.vertices))
    result["face_count"] = int(len(textured.faces))
    result["watertight"] = bool(
        trimesh.Trimesh(vertices=textured.vertices, faces=textured.faces).is_watertight
    )
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise WorkerError(EXIT_OUTPUT_MISSING, f"mesh export did not create {args.output}")
    result["output_bytes"] = args.output.stat().st_size


def _override_rembg_model(model_name: str) -> None:
    from trellis2.pipelines import rembg

    original = rembg.BiRefNet

    class ConfiguredBiRefNet(original):
        def __init__(self, model_name_from_config: str | None = None, **_: object) -> None:
            super().__init__(model_name=model_name)

    rembg.BiRefNet = ConfiguredBiRefNet


def _load_error_message(model: str, exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "gated" in lowered or "401" in text or "403" in text or "restricted" in lowered:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        detail = next((line for line in lines if "huggingface.co/" in line), lines[0] if lines else text)
        return (
            f"a gated Hugging Face dependency could not be downloaded ({detail}). "
            "TRELLIS.2 loads "
            + " and ".join(GATED_DEPENDENCIES)
            + ". Accept their terms on huggingface.co, then run `hf auth login` inside the "
            "TRELLIS.2 environment on the GPU machine."
        )
    return f"TRELLIS.2 pipeline could not be loaded from {model}: {type(exc).__name__}: {text[:800]}"


if __name__ == "__main__":
    raise SystemExit(main())
