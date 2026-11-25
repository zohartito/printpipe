"""PRP-35: locked Python dependencies and a viewer that needs no CDN."""
import hashlib
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "src/printpipe/web/static/vendor/three"
# Module specifiers of real import/export statements; comments that merely mention a URL do not count.
STATIC_IMPORT = re.compile(r"^\s*(?:import|export)\b[^;'\"]*?\bfrom\s*['\"]([^'\"]+)['\"]", re.M)
DYNAMIC_IMPORT = re.compile(r"^(?!\s*(?://|\*))[^\n]*?\bimport\s*\(\s*['\"]([^'\"]+)['\"]", re.M)


def test_prp35_python_lock_includes_hashed_build_and_mesh_dependencies():
    lock_path = ROOT / "uv.lock"
    assert lock_path.is_file(), "Missing complete dependency lock"
    lock = tomllib.loads(lock_path.read_text())
    names = {package["name"] for package in lock["package"]}
    assert {"hatchling", "editables", "pytest", "trimesh", "networkx", "manifold3d", "lxml", "numpy"} <= names
    for package in lock["package"]:
        if "registry" not in package.get("source", {}):
            continue
        artifacts = [*package.get("wheels", []), *([package["sdist"]] if "sdist" in package else [])]
        assert artifacts
        assert all(artifact.get("hash", "").startswith("sha256:") for artifact in artifacts)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert all("==" in requirement for requirement in project["build-system"]["requires"])
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert ci.count("uv export --locked") == 2 and ci.count("--require-hashes") == 2
    assert "pip install -e '.[dev,mesh-repair]'" not in ci


def test_prp35_viewer_dependencies_are_local_and_integrity_checked():
    page = (ROOT / "src/printpipe/web/run_detail.py").read_text()
    assert "https://esm.sh/" not in page
    manifest = json.loads((VENDOR / "SHA256SUMS.json").read_text())
    assert "LICENSE" in manifest
    for name, digest in manifest.items():
        path = VENDOR / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
        if path.suffix != ".js":
            continue
        text = path.read_text()
        for imported in STATIC_IMPORT.findall(text) + DYNAMIC_IMPORT.findall(text):
            assert not imported.startswith(("http:", "https:", "//")), f"{name} imports {imported}"
            if imported.startswith("."):
                assert (path.parent / imported).is_file(), f"{name} imports missing {imported}"


def test_prp35_import_map_targets_exist():
    page = (ROOT / "src/printpipe/web/run_detail.py").read_text()
    targets = re.findall(r'"(/static/vendor/three/[^"]+)"', page)
    assert targets
    for target in targets:
        path = ROOT / "src/printpipe/web" / target.removeprefix("/")
        assert path.is_file() or (target.endswith("/") and path.is_dir()), target
