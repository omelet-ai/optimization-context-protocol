# Third-party dependencies

OCP's original source is licensed under [Apache-2.0](LICENSE). Dependencies keep
their own licenses; they are installed separately and are not relicensed by OCP.
No dependency wheel, npm dependency tree, private solver or original Foundry
snapshot is distributed in this source repository.

| Direct dependency | Version | Declared license | Use |
| --- | --- | --- | --- |
| jsonschema | 4.26.0 | MIT | Python contract validation and independent checker |
| OR-Tools | 9.15.6755 | Apache-2.0 | Optional routing reference engine |
| MCP Python SDK | 2.3.0 | MIT | Optional MCP transport |
| ajv | 8.20.0 | MIT | TypeScript contract validation |
| jsonc-parser | 3.3.1 | MIT | TypeScript JSON parsing |
| TypeScript | 7.0.2 | Apache-2.0 | Build-time compiler |
| @types/node | 24.10.0 | MIT | Build-time Node type definitions |

Exact direct and transitive dependency versions are retained in the
[Python lock](tools/requirements-dev.lock) and
[npm lock](sdk/typescript/package-lock.json). Their distributions carry the
applicable license and attribution files. Redistributors bundling dependencies
must retain those files, including native-library notices in dependency wheels.
This list is not a claim that the entire dependency graph uses one license.

The local SDK, independent-checker wheel and TypeScript tarball include OCP's
LICENSE, NOTICE and this document. Building them does not publish a registry
package, GitHub Release, hosted trial or website.
