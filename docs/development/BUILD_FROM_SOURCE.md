# Build from source

Run from the repository root with Git and **Python 3.12 on PATH**, on macOS or
Linux. Python/MCP installation does not require Node. Public PyPI supplies build
and runtime dependencies. These commands build local artifacts, not registry
releases. Windows is not supported by the installer.

## Python and MCP, in one setup command

The [GitHub README](https://github.com/omelet-ai/optimization-context-protocol#first-success-from-github)
has the complete clone → install → example → MCP journey:

```sh
OCP_WORK="$(mktemp -d)"
python3.12 -B tools/quickstart.py --directory "$OCP_WORK"
cd "$OCP_WORK/kit"
```

Setup builds two Python wheels, installs both real routing engines and the
independent checker, checks MCP connectivity, and executes the diagnostics demo.
The result is JSON on stdout; installation progress goes to stderr. It makes no
model calls and does not modify host MCP configuration. The Python kit excludes
TypeScript packages and examples. `start.py`, `local_agent.py` and sample inputs
are generated kit files, not files at the repository root.

For a persistent installation, choose a new directory outside the checkout in
place of `mktemp -d`. Existing nonempty directories are rejected. Preserve the
kit path when using its generated MCP configuration. Reuse `.agent/bin/python`
to run examples; installation does not overwrite an existing environment.

## Optional complete kit with Node / TypeScript

Only this path additionally requires **Node 24/npm** on PATH and npm downloads.
From the repository root, after Python setup, build a separate full kit:

```sh
"$OCP_WORK/build/bin/python" -B tools/build_invitation_kit.py --target full --output "$OCP_WORK/node-kit"
```

The full kit adds the TypeScript package and app example. Follow its
`MULTI_DOMAIN_QUICKSTART.md` Node section and start a Python provider in a
separate terminal. The default builder target remains `full` for compatibility.
To build a Python-only kit without installing it, use `--target python`.

## Build packages separately

From the repository root (or a selected source archive) with the build Python
prepared above:

```sh
"$OCP_WORK/build/bin/python" -B tools/build_candidate.py
"$OCP_WORK/build/bin/python" -B tools/build_conformance.py
"$OCP_WORK/build/bin/python" -B tools/build_typescript.py
```

Each prints JSON identifying the artifact and SHA-256. The default output is
`.harness/work/dist/`. Python builders do not require Node; the TypeScript builder
does. A selected source archive supports these separate builders but does not
contain the complete-kit exporter. Build the kit from the GitHub checkout.

## Offline repetition and troubleshooting

For a fully offline Python setup, pass
`--offline-wheelhouse /absolute/path/to/wheels` to `tools/quickstart.py`. The
wheel directory must contain pinned build prerequisites and runtime dependencies
for the target OS, CPU and Python version. Offline mode never falls back online.

For the optional Node kit, set `OCP_NPM_CACHE` to a dedicated directory **before the first online build** if
you want to retain a known cache. Then use the same cache with
`OCP_NPM_OFFLINE=1` for the kit, or `tools/build_typescript.py --offline` for the
TypeScript builder. A missing cache fails; it never silently switches online.
`OCP_NODE` and `OCP_NPM` may specify absolute executable paths for special installs.

The first npm download includes a native TypeScript package. Online npm install
has a 300-second limit; offline install, compile and pack each have 90 seconds.
Preserve timeout output and fix network/runtime access before an explicit retry.
These preparation limits do not change the solver's computation budget.

Python build prerequisites and kit runtime dependencies need separate wheel
preparation for offline use. The kit's `start.py --offline-wheelhouse /path/to/wheels`
accepts a wheel directory for the target OS, CPU and Python version. See
[local development checks](https://github.com/omelet-ai/optimization-context-protocol/blob/main/docs/development/LOCAL_RUNTIME.md) for the checked dependency manifest.
The online README path does not require an internal cache or another checkout.

한국어: GitHub 저장소 루트에서 위 블록을 한 터미널로 실행하면 외부 임시 폴더에
꾸러미를 빌드하고 설치·실행합니다. 기본 Python·MCP 경로는 Python 3.12만 필요하며 Node/npm과 계정·키는
불필요합니다. `start.py`는 생성된 kit 안에서 실행합니다. 기존 환경은 덮어쓰지 않고,
실제 LLM 호출·사이트 배포·패키지 게시는 수행하지 않습니다.
