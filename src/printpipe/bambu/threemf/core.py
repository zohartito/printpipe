"""Stdlib-only Bambu 3MF package skeleton.

This module intentionally keeps geometry simple. Later pipeline stages can feed
real repaired mesh data into the same `MeshGeometry` shape or replace it with a
proper mesh adapter without changing the archive contract.
"""

from __future__ import annotations

import base64
import json
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BAMBU_NS = "http://schemas.bambulab.com/package/2021"

APPLICATION_PREFIX = "BambuStudio-"
DEFAULT_BAMBU_VERSION = "02.04.00.70"
DEFAULT_APPLICATION = f"{APPLICATION_PREFIX}{DEFAULT_BAMBU_VERSION}"
BAMBU_3MF_VERSION = "1"

REQUIRED_MEMBERS = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        "3D/3dmodel.model",
        "Metadata/project_settings.config",
        "Metadata/model_settings.config",
        "Metadata/slice_info.config",
        "Metadata/plate_1.png",
        "Metadata/plate_no_light_1.png",
    }
)

ET.register_namespace("", CORE_NS)
ET.register_namespace("p", PRODUCTION_NS)


@dataclass(frozen=True)
class MeshGeometry:
    """Minimal indexed triangle mesh payload for 3MF Core XML."""

    vertices: Sequence[Sequence[float]]
    triangles: Sequence[Sequence[int]]

    def __post_init__(self) -> None:
        if not self.vertices:
            raise ValueError("mesh must contain at least one vertex")
        if not self.triangles:
            raise ValueError("mesh must contain at least one triangle")

        for vertex in self.vertices:
            if len(vertex) != 3:
                raise ValueError(f"mesh vertex must have 3 coordinates: {vertex!r}")

        vertex_count = len(self.vertices)
        for triangle in self.triangles:
            if len(triangle) != 3:
                raise ValueError(f"mesh triangle must have 3 indices: {triangle!r}")
            for index in triangle:
                if index < 0 or index >= vertex_count:
                    raise ValueError(f"mesh triangle index out of range: {triangle!r}")


@dataclass(frozen=True)
class BambuProfileIds:
    """Project-level profile identifiers Bambu Studio expects in metadata."""

    filament_settings_id: str
    print_settings_id: str
    printer_settings_id: str
    printer_model: str
    printer_variant: str
    nozzle_diameter: str
    printable_height: str


@dataclass(frozen=True)
class GuiSafeTransform:
    """Keep geometry origin-centered and place it through 3MF metadata."""

    x_mm: float
    y_mm: float
    z_mm: float = 0.0
    policy: str = "gui_safe_bed_center"
    mesh_origin_policy: str = "origin_centered_z_dropped"

    @classmethod
    def bed_center(cls, bed_width_mm: float, bed_depth_mm: float, *, z_mm: float = 0.0) -> "GuiSafeTransform":
        return cls(x_mm=bed_width_mm / 2.0, y_mm=bed_depth_mm / 2.0, z_mm=z_mm)

    def build_item_transform(self) -> str:
        values = (
            "1",
            "0",
            "0",
            "0",
            "1",
            "0",
            "0",
            "0",
            "1",
            _format_number(self.x_mm),
            _format_number(self.y_mm),
            _format_number(self.z_mm),
        )
        return " ".join(values)

    def part_matrix(self) -> str:
        values = (
            "1",
            "0",
            "0",
            _format_number(self.x_mm),
            "0",
            "1",
            "0",
            _format_number(self.y_mm),
            "0",
            "0",
            "1",
            _format_number(self.z_mm),
            "0",
            "0",
            "0",
            "1",
        )
        return " ".join(values)

    def payload(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "translation_mm": [float(self.x_mm), float(self.y_mm), float(self.z_mm)],
            "mesh_origin_policy": self.mesh_origin_policy,
            "applied_in": "model_settings_and_build_item",
        }


@dataclass(frozen=True)
class ValidationResult:
    """Structural validation result for a generated Bambu 3MF bundle."""

    path: Path
    errors: tuple[str, ...]
    application: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def build_model_xml(
    mesh: MeshGeometry,
    *,
    object_name: str = "printpipe_object",
    application: str = DEFAULT_APPLICATION,
    transform: GuiSafeTransform | None = None,
) -> bytes:
    """Build minimal Bambu-native 3MF Core model XML."""

    transform = transform or GuiSafeTransform.bed_center(256, 256)
    _version_from_application(application)
    root = ET.Element(
        _q(CORE_NS, "model"),
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "xmlns:BambuStudio": BAMBU_NS,
        },
    )

    _metadata(root, "Application", application)
    _metadata(root, "BambuStudio:3mfVersion", BAMBU_3MF_VERSION)
    _metadata(root, "Title", object_name)

    resources = ET.SubElement(root, _q(CORE_NS, "resources"))
    model_object = ET.SubElement(
        resources,
        _q(CORE_NS, "object"),
        {
            "id": "1",
            "name": object_name,
            "type": "model",
            _q(PRODUCTION_NS, "UUID"): str(uuid.uuid4()),
        },
    )
    mesh_node = ET.SubElement(model_object, _q(CORE_NS, "mesh"))
    vertices = ET.SubElement(mesh_node, _q(CORE_NS, "vertices"))
    for vertex in mesh.vertices:
        x, y, z = vertex
        ET.SubElement(
            vertices,
            _q(CORE_NS, "vertex"),
            {"x": _format_decimal(x), "y": _format_decimal(y), "z": _format_decimal(z)},
        )

    triangles = ET.SubElement(mesh_node, _q(CORE_NS, "triangles"))
    for triangle in mesh.triangles:
        a, b, c = triangle
        ET.SubElement(
            triangles,
            _q(CORE_NS, "triangle"),
            {"v1": str(a), "v2": str(b), "v3": str(c)},
        )

    build = ET.SubElement(root, _q(CORE_NS, "build"), {_q(PRODUCTION_NS, "UUID"): str(uuid.uuid4())})
    ET.SubElement(
        build,
        _q(CORE_NS, "item"),
        {
            "objectid": "1",
            _q(PRODUCTION_NS, "UUID"): str(uuid.uuid4()),
            "transform": transform.build_item_transform(),
        },
    )

    return _xml_bytes(root)


def build_project_settings_config(
    profile_ids: BambuProfileIds,
    *,
    version: str = DEFAULT_BAMBU_VERSION,
    filament_settings: Mapping[str, Any] | None = None,
    process_settings: Mapping[str, Any] | None = None,
    printer_settings: Mapping[str, Any] | None = None,
) -> bytes:
    """Build flattened project settings JSON with Bambu's native header."""

    merged: dict[str, Any] = {}
    for settings in (printer_settings, process_settings, filament_settings):
        if settings:
            merged.update(settings)

    ordered: dict[str, Any] = {
        "name": "project_settings",
        "from": "project",
        "version": version,
    }
    for key, value in merged.items():
        if key not in ordered:
            ordered[key] = value

    ordered["filament_settings_id"] = [profile_ids.filament_settings_id]
    ordered["print_settings_id"] = profile_ids.print_settings_id
    ordered["printer_settings_id"] = profile_ids.printer_settings_id
    ordered["printer_model"] = profile_ids.printer_model
    ordered["printer_variant"] = profile_ids.printer_variant
    ordered["nozzle_diameter"] = [profile_ids.nozzle_diameter]
    ordered["printable_height"] = profile_ids.printable_height

    return (json.dumps(ordered, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build_model_settings_config(
    *,
    object_name: str = "printpipe_object",
    transform: GuiSafeTransform | None = None,
) -> bytes:
    """Build Bambu model metadata with an explicit GUI-safe transform payload."""

    transform = transform or GuiSafeTransform.bed_center(256, 256)
    root = ET.Element("config")
    model_object = ET.SubElement(root, "object", {"id": "1", "name": object_name})
    ET.SubElement(model_object, "metadata", {"key": "name", "value": object_name})
    ET.SubElement(model_object, "metadata", {"key": "extruder", "value": "1"})

    part = ET.SubElement(model_object, "part", {"id": "1", "subtype": "normal_part"})
    ET.SubElement(part, "metadata", {"key": "name", "value": object_name})
    ET.SubElement(part, "metadata", {"key": "matrix", "value": transform.part_matrix()})
    ET.SubElement(part, "metadata", {"key": "source_file", "value": f"{object_name}.stl"})
    ET.SubElement(part, "metadata", {"key": "source_object_id", "value": "0"})
    ET.SubElement(part, "metadata", {"key": "source_volume_id", "value": "0"})
    ET.SubElement(part, "metadata", {"key": "printpipe_transform_policy", "value": transform.policy})
    ET.SubElement(
        part,
        "metadata",
        {
            "key": "printpipe_transform",
            "value": json.dumps(transform.payload(), sort_keys=True),
        },
    )

    plate = ET.SubElement(root, "plate")
    ET.SubElement(plate, "metadata", {"key": "plater_id", "value": "1"})
    ET.SubElement(plate, "metadata", {"key": "plater_name", "value": ""})
    ET.SubElement(plate, "metadata", {"key": "locked", "value": "false"})
    ET.SubElement(plate, "metadata", {"key": "filament_map_mode", "value": "Auto For Flush"})
    ET.SubElement(plate, "metadata", {"key": "filament_maps", "value": "1"})
    instance = ET.SubElement(plate, "model_instance")
    ET.SubElement(instance, "metadata", {"key": "object_id", "value": "1"})
    ET.SubElement(instance, "metadata", {"key": "instance_id", "value": "0"})
    ET.SubElement(instance, "metadata", {"key": "identify_id", "value": "1"})

    return _xml_bytes(root)


def build_slice_info_config(
    *,
    object_name: str = "printpipe_object",
    profile_ids: BambuProfileIds,
    version: str = DEFAULT_BAMBU_VERSION,
) -> bytes:
    """Build a minimal slice info stub that names plate 1 and object 1."""

    root = ET.Element("config")
    header = ET.SubElement(root, "header")
    ET.SubElement(header, "header_item", {"key": "X-BBL-Client-Type", "value": "slicer"})
    ET.SubElement(header, "header_item", {"key": "X-BBL-Client-Version", "value": version})
    plate = ET.SubElement(root, "plate")
    ET.SubElement(plate, "metadata", {"key": "index", "value": "1"})
    ET.SubElement(plate, "metadata", {"key": "printer_model_id", "value": profile_ids.printer_model})
    ET.SubElement(plate, "metadata", {"key": "nozzle_diameters", "value": profile_ids.nozzle_diameter})
    ET.SubElement(plate, "metadata", {"key": "timelapse_type", "value": "0"})
    ET.SubElement(plate, "object", {"identify_id": "1", "name": object_name, "skipped": "false"})
    return _xml_bytes(root)


def write_bundle(
    path: str | Path,
    *,
    mesh: MeshGeometry,
    profile_ids: BambuProfileIds,
    object_name: str = "printpipe_object",
    application: str = DEFAULT_APPLICATION,
    transform: GuiSafeTransform | None = None,
    filament_settings: Mapping[str, Any] | None = None,
    process_settings: Mapping[str, Any] | None = None,
    printer_settings: Mapping[str, Any] | None = None,
) -> Path:
    """Write a minimal Bambu-native 3MF archive and return its path."""

    bundle_path = Path(path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    version = _version_from_application(application)
    transform = transform or GuiSafeTransform.bed_center(256, 256)

    members = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _RELS,
        "3D/3dmodel.model": build_model_xml(
            mesh,
            object_name=object_name,
            application=application,
            transform=transform,
        ),
        "Metadata/project_settings.config": build_project_settings_config(
            profile_ids,
            version=version,
            filament_settings=filament_settings,
            process_settings=process_settings,
            printer_settings=printer_settings,
        ),
        "Metadata/model_settings.config": build_model_settings_config(
            object_name=object_name,
            transform=transform,
        ),
        "Metadata/slice_info.config": build_slice_info_config(
            object_name=object_name,
            profile_ids=profile_ids,
            version=version,
        ),
        "Metadata/plate_1.png": _TRANSPARENT_PNG,
        "Metadata/plate_no_light_1.png": _TRANSPARENT_PNG,
    }

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in _WRITE_ORDER:
            compress_type = zipfile.ZIP_STORED if member in _STORED_MEMBERS else zipfile.ZIP_DEFLATED
            archive.writestr(member, members[member], compress_type=compress_type)

    return bundle_path


def validate_bundle(path: str | Path) -> ValidationResult:
    """Check required archive members and the Bambu Application signature."""

    bundle_path = Path(path)
    errors: list[str] = []
    application: str | None = None

    try:
        with zipfile.ZipFile(bundle_path) as archive:
            names = set(archive.namelist())
            for member in sorted(REQUIRED_MEMBERS):
                if member not in names:
                    errors.append(f"missing archive member: {member}")

            if "3D/3dmodel.model" in names:
                try:
                    root = ET.fromstring(archive.read("3D/3dmodel.model"))
                except ET.ParseError as exc:
                    errors.append(f"3D/3dmodel.model is not valid XML: {exc}")
                else:
                    application = _application_metadata(root)
                    if application is None:
                        errors.append("missing Application metadata")
                    elif not application.startswith(APPLICATION_PREFIX):
                        errors.append(
                            "Application metadata must start with "
                            f"{APPLICATION_PREFIX}; found {application}"
                        )
    except zipfile.BadZipFile:
        errors.append("not a readable zip archive")
    except FileNotFoundError:
        errors.append(f"bundle not found: {bundle_path}")

    return ValidationResult(path=bundle_path, errors=tuple(errors), application=application)


def _metadata(root: ET.Element, name: str, value: str) -> None:
    node = ET.SubElement(root, _q(CORE_NS, "metadata"), {"name": name})
    node.text = value


def _application_metadata(root: ET.Element) -> str | None:
    for metadata in root.findall(f".//{{{CORE_NS}}}metadata"):
        if metadata.attrib.get("name") == "Application":
            return metadata.text or ""
    for metadata in root.findall(".//metadata"):
        if metadata.attrib.get("name") == "Application":
            return metadata.text or ""
    return None


def _version_from_application(application: str) -> str:
    if not application.startswith(APPLICATION_PREFIX):
        raise ValueError(f"application must start with {APPLICATION_PREFIX}")
    version = application.removeprefix(APPLICATION_PREFIX)
    if not version:
        raise ValueError("application version must not be empty")
    return version


def _format_number(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _format_decimal(value: float) -> str:
    return f"{float(value):.6f}"


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _xml_bytes(root: ET.Element) -> bytes:
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root,
        encoding="utf-8",
        short_empty_elements=True,
    )


_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="config" ContentType="application/vnd.bambulab-package.config"/>
</Types>
"""

_RELS = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model" Id="rel0"/>
</Relationships>
"""

_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/"
    "HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)

_WRITE_ORDER = (
    "[Content_Types].xml",
    "_rels/.rels",
    "3D/3dmodel.model",
    "Metadata/project_settings.config",
    "Metadata/model_settings.config",
    "Metadata/slice_info.config",
    "Metadata/plate_1.png",
    "Metadata/plate_no_light_1.png",
)

_STORED_MEMBERS = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        "Metadata/model_settings.config",
        "Metadata/slice_info.config",
        "Metadata/plate_1.png",
        "Metadata/plate_no_light_1.png",
    }
)
