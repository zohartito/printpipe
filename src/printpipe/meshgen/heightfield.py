"""Dependency-free image relief mesh adapter for media meshgen smoke tests."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MAX_HEIGHTFIELD_SOURCE_BYTES = 8 * 1024 * 1024
MAX_HEIGHTFIELD_PNG_DIMENSION = 2_048
MAX_HEIGHTFIELD_PNG_PIXELS = 1_000_000
MAX_HEIGHTFIELD_PNG_IDAT_BYTES = 4 * 1024 * 1024
MAX_HEIGHTFIELD_PNG_DECOMPRESSED_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class HeightfieldOptions:
    size_mm: float = 40.0
    height_mm: float = 4.0
    base_thickness_mm: float = 1.0
    max_grid: int = 32


def write_heightfield_stl(
    *,
    source_paths: list[Path],
    output_path: Path,
    output_format: str,
    options: HeightfieldOptions = HeightfieldOptions(),
) -> Path:
    """Write an ASCII STL heightfield relief from the first supported image."""

    if output_format.lower() != "stl":
        raise ValueError("heightfield adapter currently supports STL output only")
    if not source_paths:
        raise ValueError("heightfield adapter requires at least one --source image")

    luminance = _read_luminance(source_paths[0])
    rows = _downsample(luminance, max_grid=options.max_grid)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _heightfield_to_ascii_stl(rows, options=options),
        encoding="ascii",
    )
    return output_path


def _read_luminance(path: Path) -> list[list[int]]:
    if path.stat().st_size > MAX_HEIGHTFIELD_SOURCE_BYTES:
        raise ValueError("heightfield image exceeds source byte limit")
    with path.open("rb") as source:
        data = source.read(MAX_HEIGHTFIELD_SOURCE_BYTES + 1)
    if len(data) > MAX_HEIGHTFIELD_SOURCE_BYTES:
        raise ValueError("heightfield image exceeds source byte limit")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _read_png_luminance(data)
    raise ValueError(
        f"unsupported heightfield image format for {path.name}; use PNG for local smoke"
    )


def _read_png_luminance(data: bytes) -> list[list[int]]:
    offset = 8
    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    interlace = 0
    palette: list[tuple[int, int, int]] = []
    idat = bytearray()
    seen_ihdr = False
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        payload = data[payload_start:payload_end]
        if len(payload) != length:
            raise ValueError("truncated PNG chunk payload")
        if kind == b"IHDR":
            if seen_ihdr or length != 13:
                raise ValueError("invalid PNG IHDR chunk")
            seen_ihdr = True
            width, height, bit_depth, color_type, _compression, _filter, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
        elif kind == b"PLTE":
            if not payload or len(payload) > 768 or len(payload) % 3:
                raise ValueError("invalid PNG palette")
            palette = [
                tuple(payload[index : index + 3])
                for index in range(0, len(payload) - 2, 3)
            ]
        elif kind == b"IDAT":
            if len(idat) + len(payload) > MAX_HEIGHTFIELD_PNG_IDAT_BYTES:
                raise ValueError("heightfield PNG compressed data exceeds byte limit")
            idat.extend(payload)
        elif kind == b"IEND":
            break
        offset = payload_end + 4

    if not seen_ihdr or width < 2 or height < 2:
        raise ValueError("heightfield PNG must be at least 2x2 pixels")
    if (
        width > MAX_HEIGHTFIELD_PNG_DIMENSION
        or height > MAX_HEIGHTFIELD_PNG_DIMENSION
        or width * height > MAX_HEIGHTFIELD_PNG_PIXELS
    ):
        raise ValueError("heightfield PNG dimensions exceed resource limits")
    if bit_depth != 8:
        raise ValueError("heightfield PNG must use 8-bit channels")
    if interlace:
        raise ValueError("interlaced PNG is not supported by the local heightfield adapter")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    channels = channels_by_type.get(color_type)
    if channels is None:
        raise ValueError(f"unsupported PNG color type: {color_type}")

    row_bytes = width * channels
    expected_bytes = height * (row_bytes + 1)
    if expected_bytes > MAX_HEIGHTFIELD_PNG_DECOMPRESSED_BYTES:
        raise ValueError("heightfield PNG decompressed data exceeds byte limit")
    decompressor = zlib.decompressobj()
    decompressed = decompressor.decompress(
        bytes(idat), MAX_HEIGHTFIELD_PNG_DECOMPRESSED_BYTES + 1
    )
    if (
        len(decompressed) != expected_bytes
        or decompressor.unconsumed_tail
        or not decompressor.eof
    ):
        raise ValueError("invalid or oversized heightfield PNG image data")
    rows: list[bytes] = []
    previous = bytes(row_bytes)
    cursor = 0
    for _row_index in range(height):
        filter_type = decompressed[cursor]
        cursor += 1
        scanline = bytearray(decompressed[cursor : cursor + row_bytes])
        cursor += row_bytes
        decoded = _unfilter_scanline(scanline, previous, filter_type, channels)
        rows.append(bytes(decoded))
        previous = bytes(decoded)

    return [_scanline_to_luminance(row, width, color_type, channels, palette) for row in rows]


def _unfilter_scanline(
    scanline: bytearray,
    previous: bytes,
    filter_type: int,
    bytes_per_pixel: int,
) -> bytearray:
    decoded = bytearray(len(scanline))
    for index, value in enumerate(scanline):
        left = decoded[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if index < len(previous) else 0
        upper_left = (
            previous[index - bytes_per_pixel]
            if index >= bytes_per_pixel and index - bytes_per_pixel < len(previous)
            else 0
        )
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = _paeth(left, up, upper_left)
        else:
            raise ValueError(f"unsupported PNG filter type: {filter_type}")
        decoded[index] = (value + predictor) & 0xFF
    return decoded


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_delta = abs(estimate - left)
    up_delta = abs(estimate - up)
    upper_left_delta = abs(estimate - upper_left)
    if left_delta <= up_delta and left_delta <= upper_left_delta:
        return left
    if up_delta <= upper_left_delta:
        return up
    return upper_left


def _scanline_to_luminance(
    scanline: bytes,
    width: int,
    color_type: int,
    channels: int,
    palette: list[tuple[int, int, int]],
) -> list[int]:
    values: list[int] = []
    for pixel in range(width):
        start = pixel * channels
        if color_type in {0, 4}:
            values.append(scanline[start])
        elif color_type == 3:
            index = scanline[start]
            try:
                red, green, blue = palette[index]
            except IndexError as exc:
                raise ValueError("PNG palette index is out of range") from exc
            values.append(_rgb_luminance(red, green, blue))
        else:
            red, green, blue = scanline[start : start + 3]
            values.append(_rgb_luminance(red, green, blue))
    return values


def _rgb_luminance(red: int, green: int, blue: int) -> int:
    return round((0.2126 * red) + (0.7152 * green) + (0.0722 * blue))


def _downsample(rows: list[list[int]], *, max_grid: int) -> list[list[int]]:
    source_height = len(rows)
    source_width = len(rows[0])
    target_width = max(2, min(source_width, max_grid))
    target_height = max(2, min(source_height, max_grid))
    return [
        [
            rows[round(row_index * (source_height - 1) / (target_height - 1))][
                round(col_index * (source_width - 1) / (target_width - 1))
            ]
            for col_index in range(target_width)
        ]
        for row_index in range(target_height)
    ]


def _heightfield_to_ascii_stl(
    rows: list[list[int]],
    *,
    options: HeightfieldOptions,
) -> str:
    height_count = len(rows)
    width_count = len(rows[0])
    aspect = height_count / width_count
    width_mm = options.size_mm
    depth_mm = max(1.0, options.size_mm * aspect)

    top = []
    bottom = []
    for row_index, row in enumerate(rows):
        y = -depth_mm / 2 + depth_mm * row_index / (height_count - 1)
        top_row = []
        bottom_row = []
        for col_index, value in enumerate(row):
            x = -width_mm / 2 + width_mm * col_index / (width_count - 1)
            z = options.base_thickness_mm + (value / 255.0) * options.height_mm
            top_row.append((x, y, z))
            bottom_row.append((x, y, 0.0))
        top.append(top_row)
        bottom.append(bottom_row)

    triangles: list[tuple[tuple[float, float, float], ...]] = []
    for row_index in range(height_count - 1):
        for col_index in range(width_count - 1):
            triangles.extend(
                [
                    (
                        top[row_index][col_index],
                        top[row_index][col_index + 1],
                        top[row_index + 1][col_index + 1],
                    ),
                    (
                        top[row_index][col_index],
                        top[row_index + 1][col_index + 1],
                        top[row_index + 1][col_index],
                    ),
                    (
                        bottom[row_index + 1][col_index + 1],
                        bottom[row_index][col_index + 1],
                        bottom[row_index][col_index],
                    ),
                    (
                        bottom[row_index + 1][col_index],
                        bottom[row_index + 1][col_index + 1],
                        bottom[row_index][col_index],
                    ),
                ]
            )

    for col_index in range(width_count - 1):
        triangles.extend(
            [
                (
                    bottom[0][col_index],
                    top[0][col_index + 1],
                    top[0][col_index],
                ),
                (
                    bottom[0][col_index],
                    bottom[0][col_index + 1],
                    top[0][col_index + 1],
                ),
                (
                    bottom[-1][col_index],
                    top[-1][col_index],
                    top[-1][col_index + 1],
                ),
                (
                    bottom[-1][col_index],
                    top[-1][col_index + 1],
                    bottom[-1][col_index + 1],
                ),
            ]
        )

    for row_index in range(height_count - 1):
        triangles.extend(
            [
                (
                    bottom[row_index][0],
                    top[row_index][0],
                    top[row_index + 1][0],
                ),
                (
                    bottom[row_index][0],
                    top[row_index + 1][0],
                    bottom[row_index + 1][0],
                ),
                (
                    bottom[row_index][-1],
                    top[row_index + 1][-1],
                    top[row_index][-1],
                ),
                (
                    bottom[row_index][-1],
                    bottom[row_index + 1][-1],
                    top[row_index + 1][-1],
                ),
            ]
        )

    lines = ["solid printpipe_heightfield"]
    for triangle in triangles:
        lines.extend(_triangle_to_stl_lines(triangle))
    lines.append("endsolid printpipe_heightfield")
    return "\n".join(lines) + "\n"


def _triangle_to_stl_lines(
    triangle: tuple[tuple[float, float, float], ...],
) -> list[str]:
    return [
        "  facet normal 0 0 0",
        "    outer loop",
        *[
            f"      vertex {x:.6f} {y:.6f} {z:.6f}"
            for x, y, z in triangle
        ],
        "    endloop",
        "  endfacet",
    ]
