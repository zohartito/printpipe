"""Regression coverage for the confirmed public repository audit."""
from pathlib import Path

import pytest

from printpipe.contracts import StageStatus
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline

FIXTURE = Path(__file__).parent / 'fixtures/objects/existing_stl_pipeline/tiny_tetrahedron.stl'


def test_prp01_generated_3mf_round_trip(tmp_path):
    first = run_existing_mesh_pipeline(FIXTURE, tmp_path / 'first')
    bundle = next(first.layout.bundle_dir.glob('*.3mf'))
    second = run_existing_mesh_pipeline(bundle, tmp_path / 'second')
    assert next(second.layout.bundle_dir.glob('*.3mf')).is_file()
    assert (second.layout.reports_dir / 'run_report.json').is_file()


def test_prp01_missing_loader_writes_failed_run_report(tmp_path, monkeypatch):
    from printpipe.mesh import repair

    source = tmp_path / 'input.3mf'
    source.write_bytes(b'loader-test')

    def missing_loader(*args):
        raise ModuleNotFoundError("No module named 'lxml'", name='lxml')

    monkeypatch.setattr(repair, '_load_mesh', missing_loader)
    with pytest.raises(PipelineError) as error:
        run_existing_mesh_pipeline(source, tmp_path / 'runs')
    result = error.value.result
    receipt = next(s for s in result.stages if s.stage == 'mesh_repair')
    assert receipt.status == StageStatus.FAILED
    assert 'lxml' in receipt.message
    assert (result.layout.reports_dir / 'run_report.json').is_file()


@pytest.mark.parametrize('extents', [(400, 400, 10), (20, 20, 500)])
def test_prp02_oversized_mesh_stops_before_bundle(tmp_path, extents):
    import trimesh

    source = tmp_path / 'oversized.stl'
    trimesh.creation.box(extents=extents).export(source)
    with pytest.raises(PipelineError, match='envelope') as error:
        run_existing_mesh_pipeline(source, tmp_path / 'runs')
    result = error.value.result
    assert not list(result.layout.bundle_dir.glob('*.3mf'))
    import json
    fit = json.loads((result.layout.reports_dir / 'bed_fit.json').read_text())
    assert fit['fit']['fits'] is False
    report = json.loads((result.layout.reports_dir / 'run_report.json').read_text())
    assert report['warnings']


def test_prp03_non_manifold_mesh_stops_before_bundle(tmp_path):
    import trimesh

    first = trimesh.creation.box(extents=(10, 10, 10))
    second = first.copy()
    second.apply_translation((10, 10, 0))
    source = tmp_path / 'shared_edge.stl'
    trimesh.util.concatenate([first, second]).export(source)
    with pytest.raises(PipelineError, match='non-manifold') as error:
        run_existing_mesh_pipeline(source, tmp_path / 'runs')
    assert not list(error.value.result.layout.bundle_dir.glob('*.3mf'))
    assert (error.value.result.layout.reports_dir / 'run_report.json').is_file()


def test_prp13_settings_delta_matches_final_bundle(tmp_path):
    import json
    import zipfile

    result = run_existing_mesh_pipeline(FIXTURE, tmp_path / 'runs', material='PETG',
                                        process_overrides={'wall_loops': ['7']})
    changes = json.loads((result.layout.reports_dir / 'run_report.json').read_text())['settings_changes']
    by_key = {change['key']: change for change in changes}
    with zipfile.ZipFile(next(result.layout.bundle_dir.glob('*.3mf'))) as archive:
        settings = json.loads(archive.read('Metadata/project_settings.config'))
    for key in ('wall_loops', 'filament_settings_id', 'nozzle_temperature'):
        assert by_key[key]['to'] == settings[key]
        assert by_key[key]['from'] != by_key[key]['to']
    assert by_key['wall_loops']['reason'] == 'user process override'
    assert 'material' in by_key['nozzle_temperature']['reason']
