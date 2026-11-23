# OCP specifications and compatibility

OCP is a public developer preview. Choose the contract that matches your work.
내 알고리즘을 서버로 만들 때는 서버 패키지 명세와 제작 예제에서 시작하세요.

| Contract | What it defines | Where to start |
| --- | --- | --- |
| Core 0.1 | Capabilities, requirements, requests, results and evaluation. Profiles supply units, objectives and constraints. | [Core specification](core/CORE_0_1.md) · [Core schema](schemas/core-0.1.schema.json) · [Synchronous execution profile](execution/SYNC_0_1.md) |
| Native v1 | The versioned catalog, job and error contract used by the Native SDK and its MCP binding. | [Native binding](bindings/FOUNDRY_NATIVE_V1_CANDIDATE.md) · [Native preview installation](../docs/users/NATIVE_ROUTING_QUICKSTART.md) |
| Generic OCP Server package | The descriptor declares the engine's API, inputs, return values, units and supported capabilities. The template packages the author's connector and optional checker. | [Package descriptor](server-package/README.md) · [Descriptor schema](schemas/server-package-0.1.schema.json) · [Build a server](../examples/cutting-stock/README.md) |

The [IB-1.2 baseline](../docs/development/TEMPLATE_INTEGRATION_BASELINE_IB12.md) records
the generic descriptor, template and runtime versions that work together. The
[compatibility policy](../docs/users/COMPATIBILITY.md) covers changes to contract
meaning. Each package advertises the [file formats](input-formats/README.md),
[playbooks](playbooks/README.md) and [operations](operations/README.md) that it supports.
Applications select an available binding such as MCP for AI clients.
