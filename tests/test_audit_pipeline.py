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
