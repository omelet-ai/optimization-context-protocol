# Build a cutting-stock OCP Server

Start with a Python function that cuts ordered pieces from identical bars. Package it
with the public template and ask a desktop AI client to submit an order. The server
returns a job ID, a layout and an independent check of the minimum bar count.
The local build and SDK walkthrough use Python 3.12, public Python dependencies and
the source checkout. A desktop account is needed only for the optional chat step.

## 1. Build from public source

Run these commands from the root of a fresh checkout in one terminal. If you
already built this example, activate its environment and continue at step 3.

```sh
git clone https://github.com/omelet-ai/optimization-context-protocol.git
cd optimization-context-protocol
```

<!-- ocp:cutplan-build -->
```sh
python3.12 -m venv .harness/work/cutplan-demo/venv
. .harness/work/cutplan-demo/venv/bin/activate
python -m pip install "build==1.4.0" "setuptools==80.9.0" "wheel==0.46.3"
python tools/build_candidate.py
python -m pip install --find-links .harness/work/dist "ocp-candidate[server]==0.4.0.dev12+publicformat3"
python -I -B -m ocp_runtime.authoring init --name cutplan --content examples/cutting-stock/content --output .harness/work/cutplan-demo/server
python -m build --wheel --no-isolation --outdir .harness/work/dist .harness/work/cutplan-demo/server
python -m pip install --find-links .harness/work/dist .harness/work/dist/cutplan-0.1.0.dev3-py3-none-any.whl
```

## 2. Configure one local instance

Use the same configuration and state directory for the desktop app and the lookup
command. Keep this directory when reopening the app to retrieve an earlier job.

<!-- ocp:cutplan-config -->
```sh
python - <<'PY'
import json
from pathlib import Path
work = Path(".harness/work/cutplan-demo").resolve()
state = work / "state"
state.mkdir(mode=0o700, exist_ok=True)
config = json.loads((work / "server/config.example.json").read_text())
config.update(connector_factory="ocp_cutplan.content.adapter:create_bundle", state_directory=str(state))
with (work / "config.json").open("x", encoding="utf-8") as target:
    json.dump(config, target, indent=2)
PY
cutplan check
cutplan doctor --config .harness/work/cutplan-demo/config.json
cutplan host-config --config .harness/work/cutplan-demo/config.json
```

`doctor` should report `READY`, with zero engine calls. The final command prints
the `mcpServers` launch entry for a local stdio host.

## 3. Submit an order and check the result

<!-- ocp:cutplan-orders -->
```sh
python examples/cutting-stock/order.py --config .harness/work/cutplan-demo/config.json --pieces 60 50 30 20 20 20
python examples/cutting-stock/order.py --config .harness/work/cutplan-demo/config.json --pieces 60 50 30 21 20 20
```

The first order needs **two 100 cm bars**. Cut 60+20+20 and 50+30+20. The second needs
**three** because the pieces now total 201 cm. Each submission receives its own ID.
The checker verifies the bar count, ordered quantities, capacity and minimum number
of bars using a separate partition search. Equivalent layouts and row order are valid.

## 4. Ask a desktop client

Add the launch entry from step 2 to your local stdio MCP host and enable the server
in the conversation. In the tested macOS desktop setups, ChatGPT Work/Codex used
its local MCP configuration and Claude Desktop used its local MCP server settings.
Fully restart Claude Desktop after editing its configuration. Allow the requested
tools for this order when the app asks.

> Use the connected cutting-stock server to submit this order. Stock bars are 100 cm.
> Cut one piece of each listed length: 60, 50, 30, 20, 20, 20 cm. Kerf is zero.
> Give me the server job ID, the minimum bar count, the layout and its independent checks.

> 연결된 절단 서버에 실제로 제출해 줘. 원자재는 100cm이고 필요한 조각은
> 60, 50, 30, 20, 20, 20cm야. 절단 손실은 0cm야. 서버가 반환한 작업 ID,
> 최소 원자재 개수, 절단 배치와 독립 검산 결과를 알려줘.

Put the ID from the **app's answer** in the command below. It only reads that job.

```sh
python examples/cutting-stock/order.py --config .harness/work/cutplan-demo/config.json --job-id YOUR_JOB_ID
```

A successful first integration has the same job ID, count, layout and passing
checks in the app and in the lookup. Both desktop clients solved the small
baseline and changed orders without submitting a job when simply asked for the
math. Both submitted and returned a matching ID when explicitly asked to use the
server. These observations cover this synthetic example on the two desktop hosts.

## Put your engine in its place

| File | Responsibility |
| --- | --- |
| [algorithm.py](content/algorithm.py) | Original optimization function, independent of OCP. |
| [manifest.json](content/manifest.json) | Input, units, objective, supported conditions and result shape. |
| [adapter.py](content/adapter.py) | Exposes the declared contract and calls the function. |
| [checker.py](content/checker.py) | Checks the returned layout and independently computes the minimum. |

This example accepts 1–12 pieces, integer centimetres, one stock size and zero kerf.
Ask for the stock length if it is missing. Multiple stock sizes, prices or nonzero
kerf require a supporting engine and contract. After editing content, generate a
new output directory and rebuild the wheel. See the [authoring guide](../../docs/users/SERVER_FORMAT_PREVIEW.md)
and the [pinned integration baseline](../../docs/development/TEMPLATE_INTEGRATION_BASELINE_IB12.md).
