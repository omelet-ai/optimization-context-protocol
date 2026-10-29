# Start with the OCP native developer preview

Use the native ZIP and `SHA256SUMS` from the
[v0.1.1-preview.1 prerelease](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1). Run
`shasum -a 256 ocp-native-v0.1.1-preview.1.zip` (or Linux `sha256sum`) and compare
the result with the matching filename in `SHA256SUMS` before extracting.
Checksums detect changed bytes; they are not signatures. Locally rebuilt kits
have their own hashes and are not the published artifact.

## Your first result

Extract the native ZIP into a new directory and open a terminal there. You need
Python 3.12 on macOS or Linux, and public PyPI access for dependencies. No Node,
Foundry checkout, Omelet key, or model call is needed for Python and MCP.

```sh
python3.12 -B install.py
.native/bin/python -I -B demo.py
.native/bin/python -I -B mcp_config.py
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --input worker-input.json
```

The demo runs three real jobs and independent checks: routing cost 18 meters,
worker cost 7 cost units and inventory cost 16 cost units. Read mathematical
status separately from job status. `feasible` does not mean `optimal`.
MCP configuration is printed for review; the command does not edit your host or
call a language model. Install on the machine where your MCP host runs.

If Python is missing or the version is wrong, use Python 3.12 first. If an
existing environment previously installed successfully, check it with
`.native/bin/python -m pip check` and reuse it. An environment left by a failed
installation is not ready: preserve the failure and choose a new `--venv` path
after correcting the reported cause. An offline wheelhouse must contain all
pinned dependencies for your platform. Commands for a custom environment must
use that environment's `bin/python` instead of `.native/bin/python`.

## Apply a problem

Read `WORKED_EXAMPLES.md` to change a problem in each of the three domains.
Use `INSPECTION_GUIDE.md` for CSV → fixed-time inspection assignment → workload
tables → scenario comparison. Use `PROJECT_GUIDE.md`, `BYO_WORKER.md` and
`PROFILE_EXTENSION.md` for your own project, engine and profile.

The reference worker profile is bounded to 8 tasks and 4 workers. Travel,
breaks, shift generation and fairness are not supported. Routing and inventory
also have explicit limits; inspect the advertised capabilities first. This is
a developer preview, not a production scheduling service or a certified engine.

## Independent review

Follow `EXTERNAL_EVALUATION.md` without maintainer assistance first. Copy
`REVIEW_FORM.json`, enter the received archive's SHA-256 and your environment,
then record each task's outcome and help needed. Use synthetic data only.
`own-application` and `own-engine` require your own integration; running the
bundled examples alone does not satisfy them. The project owner separately
reviews the inspection assignments against the stated business requirements.

No participant completion is assumed. Return findings through your original
invitation channel; public non-sensitive bugs can use the repository's Issues.
Never submit keys, customer data, local credentials or a full HOME directory.
Model execution and service trials require separately scoped approval.

Validation targets are macOS arm64 and Linux amd64 Docker emulation, Python
3.12; optional TypeScript uses Node 24 on macOS. Windows, native Linux arm64
and Linux Node are unverified. The exact candidate's test report determines
which targets actually passed. Automated tests cannot establish human acceptance.
