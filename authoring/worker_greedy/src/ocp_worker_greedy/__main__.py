"""Run the BYO provider through the unchanged native MCP tool implementation."""
from ocp_runtime.native_mcp import create_native_mcp
from ocp_runtime.native_server import LocalAPI
from .registration import registration


def main():
    with LocalAPI([registration()]) as local:
        create_native_mcp({'worker-scheduling': local.client('worker-scheduling')}).run(transport='stdio')


if __name__ == '__main__':
    main()
