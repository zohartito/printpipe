from printpipe.cli import main
from printpipe.config import configured_media_meshgen_command


def test_prp09_configure_prints_reviewed_trust_handoff(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('PRINTPIPE_CONFIG_PATH', raising=False)
    monkeypatch.delenv('PRINTPIPE_TRUST_PROJECT_MEDIA_COMMAND', raising=False)
    monkeypatch.delenv('PRINTPIPE_MEDIA_MESHGEN_COMMAND', raising=False)
    assert main(['media-meshgen-configure', '--command', 'printpipe media-meshgen-heightfield']) == 0
    assert configured_media_meshgen_command() == ''
    output = capsys.readouterr().out
    assert 'PRINTPIPE_CONFIG_PATH' in output
    assert 'review' in output.lower()
    monkeypatch.setenv('PRINTPIPE_CONFIG_PATH', str(tmp_path / '.printpipe/config.json'))
    assert configured_media_meshgen_command() == 'printpipe media-meshgen-heightfield'
