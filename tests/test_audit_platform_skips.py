"""Native checks must report skipped when their platform tool is unavailable."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize('filename,name,needs_capsys', [
    ('test_packaging_macos_app.py', 'test_build_macos_app_bundle_can_apply_ad_hoc_signature', False),
    ('test_packaging_macos_dmg.py', 'test_build_macos_dmg_package_wraps_app_in_drag_install_image', False),
    ('test_packaging_macos_dmg.py', 'test_cli_build_macos_dmg_json_reports_distribution_artifact', True),
    ('test_packaging_release.py', 'test_build_release_bundle_writes_manifest_with_checksums', False),
    ('test_packaging_release.py', 'test_cli_build_release_json_reports_manifest', True),
    ('test_packaging_release.py', 'test_build_release_bundle_can_include_macos_standalone_runtime_zip', False),
])
def test_prp25_missing_native_tool_is_an_explicit_skip(tmp_path, monkeypatch, capsys, filename, name, needs_capsys):
    spec = importlib.util.spec_from_file_location('native_check', Path(__file__).parent / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, 'which', lambda _: None)
    kwargs = {'tmp_path': tmp_path}
    if needs_capsys:
        kwargs['capsys'] = capsys
    if 'standalone' in name:
        kwargs['monkeypatch'] = monkeypatch
    with pytest.raises(pytest.skip.Exception):
        getattr(module, name)(**kwargs)
