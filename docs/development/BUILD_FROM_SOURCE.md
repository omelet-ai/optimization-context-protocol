# Build from source

Run from the repository root. You need Git, **Python 3.12 and Node 24/npm on
PATH**, on macOS or Linux. Dependency installation contacts public PyPI/npm;
no company account or OCP key is needed. These commands build local artifacts,
not registry releases. Windows is not supported by the kit installer.

## Build the complete kit

The [GitHub README](https://github.com/omelet-ai/optimization-context-protocol#first-success-from-github) has the complete clone → build → install → example
→ MCP path. This is its build step, with output kept outside the source tree:

```sh
OCP_WORK="$(mktemp -d)"
python3.12 -m venv "$OCP_WORK/build"
"$OCP_WORK/build/bin/python" -m pip install --no-compile build==1.4.0 setuptools==80.9.0 wheel==0.46.3
"$OCP_WORK/build/bin/python" -B tools/build_invitation_kit.py --output "$OCP_WORK/kit"
cd "$OCP_WORK/kit"
python3.12 start.py --mcp --venv .agent
```

Use the same terminal for the block. The builder produces all three packages and
copies documentation, apps and sample inputs into the kit. **Do not run the
builder as a bare executable**; invoke it with the build environment's Python.
`start.py`, `local_agent.py` and `basic-input.json` exist in the resulting kit,
not at the repository root. Node is required to build the complete kit, even for
Python-only use. Once built, the Python/MCP examples do not need Node.

For a persistent installation, set `OCP_WORK` to a new directory outside the
checkout instead of using `mktemp -d`. Existing nonempty kit directories and
installed environments are not overwritten. Keep the kit in place when using an
MCP configuration generated from it; regenerate the configuration after moving it.

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

Set `OCP_NPM_CACHE` to a dedicated directory **before the first online build** if
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
꾸러미를 빌드하고 설치·실행합니다. Python 3.12와 Node 24/npm이 필요하며 계정·키는
불필요합니다. `start.py`는 생성된 kit 안에서 실행합니다. 기존 환경은 덮어쓰지 않고,
실제 LLM 호출·사이트 배포·패키지 게시는 수행하지 않습니다.
