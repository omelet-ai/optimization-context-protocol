import argparse
import json
from .scaffold import create_project, strip_content, inject_content, ScaffoldError


def main():
    p = argparse.ArgumentParser(description="Create an independent OCP Server from domain content")
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("--output", required=True); init.add_argument("--name", required=True); init.add_argument("--content")
    strip = commands.add_parser("strip"); strip.add_argument("--project", required=True); strip.add_argument("--output", required=True)
    inject = commands.add_parser("inject"); inject.add_argument("--project", required=True); inject.add_argument("--content", required=True); inject.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        if a.command == "init": record = create_project(a.output, a.name, content=a.content)
        elif a.command == "strip": record = strip_content(a.project, a.output)
        else: record = inject_content(a.project, a.content, a.output)
        print(json.dumps({"status": "CREATED", "output": a.output, "template_revision": record["parameters"]["template_revision"]}))
        return 0
    except (ScaffoldError, OSError, ValueError) as e:
        print(json.dumps({"status": "ERROR", "message": str(e)}))
        return 2


raise SystemExit(main())
