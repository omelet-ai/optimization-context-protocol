# Inventory lot sizing

This example authors a server with a small integer optimizer. Its manifest describes the API and the executable `compare-storage-limits` playbook. The solver minimizes ordering and holding costs for a fixed demand.

From the root of the public source checkout, use a Python 3.12 environment with the OCP runtime, its MCP extra, pip and the locked wheel build tools installed:

```sh
python -IB tests/installed/test_lot_sizing_playbook.py /tmp/new-ocp-inventory-run
```

Supply a new directory for each run. The command creates the project with the public authoring API, builds and installs the wheel in the current environment, connects using MCP stdio, and runs the advertised playbook. With demand 36, ordering fee 9 and holding fee 2, the respective minimum costs for capacities 4, 7 and 12 are 87, 64 and 49. The check enumerates the feasible quantities independently and verifies the child jobs after a replay.

To author a variation, start from the files in `content/`:

```sh
python -Im ocp_runtime.authoring init --name inventory-example --output ./inventory-example --content examples/inventory-lot-sizing/content
```

The application discovers the playbook, input fields and metrics in the installed package. The solver and its independent checker are in `content/engine.py`.
