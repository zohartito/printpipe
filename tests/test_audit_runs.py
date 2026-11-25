from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from printpipe.runs import paths


@pytest.mark.parametrize('prompt', [False, True])
def test_prp16_n1_automatic_run_ids_are_atomic(tmp_path, monkeypatch, prompt):
    source = tmp_path / 'box.stl'
    source.write_text('solid box\nendsolid box\n')
    monkeypatch.setattr(paths, 'make_run_id', lambda _: 'fixed-second-box')
    def create(_):
        if prompt:
            return paths.create_prompt_run('box', tmp_path / 'runs')
        return paths.create_run(source, tmp_path / 'runs')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, range(4)))
    results.append(create(4))
    assert len({r.run_id for r in results}) == 5
    assert all(r.manifest_path.exists() for r in results)
    with pytest.raises(FileExistsError):
        paths.create_run(source, tmp_path / 'runs', run_id=results[0].run_id)
