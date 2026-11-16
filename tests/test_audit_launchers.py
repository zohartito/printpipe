import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def test_prp14_mcp_registration_is_portable():
    config = json.loads((REPO / '.mcp.json').read_text())['mcpServers']['printpipe-slicer']
    absolute = Path(config['command']).is_absolute()
    assert absolute is False, 'MCP registration must not name an owner checkout'
    proc = subprocess.run([config['command'], *config['args']], cwd=REPO,
                          input='{"id":1,"method":"initialize"}\n',
                          text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['result']['serverInfo']['name'] == 'printpipe-slicer'


def test_prp21_watch_plist_uses_checkout_and_explicit_executables(tmp_path):
    import plistlib

    generator = REPO / 'tools/generate_watch_plist.py'
    assert generator.is_file(), 'Public watch registration needs a checkout-specific generator'
    output = tmp_path / 'watch.plist'
    slicer = tmp_path / 'synthetic-slicer'
    slicer.write_text('test-only, never executed')
    proc = subprocess.run([sys.executable, str(generator), '--python', sys.executable,
                           '--bambu-cli', str(slicer), '--inbox', str(tmp_path / 'inbox'),
                           '--output', str(output)], text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    payload = plistlib.loads(output.read_bytes())
    assert payload['ProgramArguments'][:2] == [sys.executable, str(REPO / 'tools/watch_3mf_queue.py')]
    assert payload['EnvironmentVariables']['PRINTPIPE_BAMBU_STUDIO_CLI'] == str(slicer)
    assert payload['WatchPaths'] == [str(tmp_path / 'inbox')]
    assert not Path(payload['StandardOutPath']).is_relative_to(tmp_path / 'inbox')
    assert 'FILL_ME_IN' not in output.read_text()
