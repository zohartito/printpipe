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
