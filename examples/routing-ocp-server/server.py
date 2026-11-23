from pathlib import Path
from ocp_runtime.server_project import project_main


def main():
    return project_main(Path(__file__).resolve().parent, package=__package__)


if __name__ == "__main__":
    raise SystemExit(main())
