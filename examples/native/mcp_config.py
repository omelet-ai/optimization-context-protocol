"""Print configuration for this installed environment; never edits a host."""
import sys

if __name__ == '__main__':
    from ocp_runtime.native_cli import main
    raise SystemExit(main(['config', *sys.argv[1:]]))
