"""Print configuration for this installed environment; never edits a host."""
import json
from pathlib import Path
import sys

if __name__ == '__main__':
    from ocp_runtime.native_mcp import create_native_mcp  # fail now if installation is incomplete
    print(json.dumps({'mcpServers': {'ocp-native-local': {
        'command': str(Path(sys.executable).absolute()),
        'args': ['-I', '-B', '-m', 'ocp_runtime.native_mcp']}}}, indent=2))
