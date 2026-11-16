"""Start the slicer server from this checkout, preferring its virtual environment."""
from pathlib import Path
import os
import runpy
import sys

root = Path(__file__).resolve().parents[1]
python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if python.is_file() and Path(sys.prefix).resolve() != (root / '.venv').resolve():
    os.execv(str(python), [str(python), str(Path(__file__).resolve())])
os.chdir(root)
os.environ.setdefault('PRINTPIPE_MCP_INPUT_ROOT', str(root))
os.environ.setdefault('PRINTPIPE_MCP_OUTPUT_ROOT', str(root / 'runs'))
sys.path.insert(0, str(root / 'src'))
runpy.run_module('printpipe.mcp_server', run_name='__main__')
