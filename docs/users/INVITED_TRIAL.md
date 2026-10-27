# OCP developer kit

Use OCP from your own application or connect your own optimization engine. This is
a locally built evaluation artifact, not a published registry release. A trial account
or `session.json` is **not required** for the local and bring-your-engine paths.
한국어 초대 시험 안내는 이 문서 아래에, 앱·엔진 개발 안내는 `DEVELOPER_GUIDE.md`에 있습니다.

## Choose your starting path

| Path | What you need | Start here |
| --- | --- | --- |
| Try Omelet — recommended when an invitation is available | An active invitation and a private `session.json` from your inviter | Invited trial below |
| Run locally | Python 3.12; public Python dependency downloads | Local reference below |
| Bring your engine | Python 3.12; your calculation code | Your own engine below; no Omelet, OR-Tools or MCP required |

Run every command from the directory where you extracted this kit. The verified
full regression platform is Python 3.12 on macOS Apple Silicon. The first-success
command also ran in a Python 3.12.15 Linux x86_64 container on Docker Desktop
(macOS arm64 host). That is not a native Linux or full Linux trial test. Additional MCP/Python/Node
rehearsals must identify the exact ZIP hash in the supplied verification report.
Node 24 is needed only for the TypeScript example. The installer does not support
Windows. If `python3.12` is unavailable, install Python 3.12 or
use its absolute executable path. Check the version before continuing.

```sh
python3.12 --version
python3.12 install.py --check
```

The check verifies the included files, not installation or a running engine.
Compare the ZIP's SHA-256 with the value supplied through your trusted delivery
channel. A checksum detects changes; it does not authenticate the publisher.
Verify and install before editing included files. Create new files for your work.

## Local reference: no key or session file

```sh
python3.12 start.py --venv .local
```

This verifies kit hashes, creates a new environment, and runs the same application
and input with **two actual engines**: OR-Tools and the small enumerating library.
Both results are independently checked. The bundled four-visit problem has a
hand-checked cost of 18 meters. Feasible does not mean proven optimal; other
inputs need not produce identical routes or costs across engines.

The report also shows unsupported-unit rejection, deliberate capacity/visit/cost
corruption caught by the independent checker, and an actual 1 ms library deadline.
A timeout may retain a feasible solution or return unknown. No timeout is mocked.
Failure probes use separate synthetic inputs, not your data.

The command downloads pinned public dependencies but calls no remote engine.
For an offline install, add `--offline-wheelhouse /path/to/reviewed-wheels`.
Existing environments are preserved. Rerun without installing:

```sh
.local/bin/python -B demo.py --diagnostics
.local/bin/python -B own_app.py --input basic-input.json --request-id local-first --trace local-first.json
```

The second command saves a new request/result trace. `demo.py` itself writes no
trace files. To swap engines explicitly, use `demo.py --engine own` or
`demo.py --engine reference`. With `--input my-input.json`, the same app uses your
input. The own-engine example supports at most six visits and three vehicles.

Copy `basic-input.json` to a new file and change demands or capacities. Added or
renamed visits also require matching `matrix.node_ids` and matrix rows/columns.
The profile uses kg and an explicit integer meter matrix. Unsupported units,
constraints and objectives are rejected. `input.json` is a different coordinate
profile for the invited trial; do not substitute it in the local example.

## Your own engine: replace the calculation

For a local LLM connection use `python3.12 start.py --mcp --venv .agent` and follow
`LLM_QUICKSTART.md`. This includes both the local engine and MCP, with doctor,
one-solve smoke and config generation. No model is called by these checks.

```sh
python3.12 -m venv .byo
.byo/bin/python -m pip install --no-compile -c constraints.txt ./ocp_candidate-0.1.0-py3-none-any.whl ./ocp_conformance_candidate-0.1.0-py3-none-any.whl
.byo/bin/python -B byo_library.py basic-input.json --trace own-engine-trace.json
.byo/bin/python -B export_transcript.py --trace own-engine-trace.json --artifact byo_library.py --out own-engine-transcript.json
.byo/bin/python -B -m conformance.runner --bundle own-engine-transcript.json --artifact byo_library.py
```

Copy `byo_library.py` to `my_engine.py` and replace `EnumeratingLibrary.solve(problem,
time_limit_ms)` with your algorithm. Preserve `name`, `version` and the
`Outcome(solution, termination, objective)` return shape. A solution contains
`routes`, each with a `vehicle_id` and an ordered list of visit IDs. Extend
`OwnLibraryAdapter.validate` to reject unsupported inputs. The teaching adapter
supports at most six visits and three vehicles.

Run your changed file on a new synthetic input and a deliberately unsupported
case. Export the new trace with `--artifact my_engine.py`; the checker verifies
that transcript against the exact artifact hash. It does not certify every engine
behavior or prove that a particular artifact produced a transcript. A heuristic
that finds no solution must retain unknown; it has not proved infeasibility.

## Your own application

`own_app.py` shows discovery → requirements → validation → execution → evaluation
→ independent checking. Replace its input loading and presentation with your app
logic. Keep response kinds, result statuses and metric statuses; an unevaluated
null value must not become zero. Only evaluate a non-null solution.

For Node, complete the local reference install above, then:

```sh
node --version
npm install --no-save --package-lock=false --ignore-scripts --no-audit --no-fund ./ocp-candidate-0.1.0.tgz
npm run build
```

Terminal A:

```sh
.local/bin/python -B -m ocp_runtime.http_server --port 8765
```

Terminal B:

```sh
node dist/main.js http://127.0.0.1:8765 basic-input.json --request-id my-ts-job-1
node own_app.cjs http://127.0.0.1:8765 basic-input.json my-node-app-1
```

In your Node code, use `Client.connect(endpoint)`, `request(input, configuration,
requestId)`, `validate(request)`, `execute(request)`, and
`evaluate(request, result.solution)`. Check response kinds at each step. The SDK
is for server-side Node; do not expose a trial key in browser code.

`own_app.cjs` includes explicit validation and provider evaluation. Its PASS does
not claim independent verification. Use the conformance package to check its
request/response separately. Evaluation tasks and a feedback template are included
as `EVALUATION_TASKS.md` and `FEEDBACK_TEMPLATE.md`; no feedback is uploaded.

## Output files and recovery

Use a new trace/transcript filename for each run. Existing files are preserved.
`TRACE_EXISTS` means choose a new `--trace` filename; `TRACE_DIRECTORY_MISSING`
means create its parent directory or choose an existing directory.
`TRACE_WRITE_FAILED` means check directory permissions. These are local file
problems, not invitation errors. If execution may already have happened, preserve
the request ID. Use a new ID only for a genuinely new problem, not to automatically
retry an uncertain request. Stop a local provider with Ctrl+C when finished.

## Invited trial

Only this path needs the inviter's private `session.json`. Check the supplied
endpoint, active period and usage limits with the inviter. Never paste keys into
chat, screenshots or Git. Do not invent an endpoint or reuse an internal token.

```sh
python3.12 install.py --venv .venv
chmod 600 session.json
.venv/bin/python -B -m ocp_runtime.trial_client --session session.json doctor
.venv/bin/python -B main.py --session session.json --input input.json --request-id first-synthetic-run
```

Doctor checks authenticated discovery without consuming a solve. The trial uses
synthetic coordinate inputs and bounded usage. Do not submit customer or personal
data. An inactive or missing invitation does not block the independent local and
own-engine paths. The detailed invitation policy and MCP setup follow in Korean.

## OCP 초대 시험 시작하기 — 한국어

운영자에게 받은 시험용 설치 꾸러미와 개인별 `session.json`을 사용한다. 공개 registry에 올라간 정식 제품은 아니다. 운영자가 접근 주소·기간·지원 창구를 안내한 초대 시험에만 사용한다. 최초 검증 환경은 Python 3.12 / macOS Apple Silicon이며 다른 OS는 별도 검증 대상이다.

1. 꾸러미를 새 작업 폴더에 푼다. `python3.12 --version`으로 3.12를 확인한다. 명령이 없으면 Python 3.12를 설치하거나 기존 실행 파일의 절대 경로를 사용한다. `python3 --version`이 3.12인 경우에만 아래 명령을 python3로 바꿀 수 있다. Python 설치: https://www.python.org/downloads/ . Windows installer는 지원하지 않는다. Python 3.12로 설치한다. 설치기는 포함 파일 hash를 확인하고 새 가상환경에 MCP client와 독립 checker를 설치한다. OR-Tools나 Foundry 설치는 필요 없다. 공개 Python dependency 다운로드에는 인터넷이 필요하다.

```sh
python3.12 install.py --check
python3.12 install.py --venv .venv
chmod 600 session.json
.venv/bin/python -B -m ocp_runtime.trial_client --session session.json doctor
```

`doctor`는 인증·계약 일치만 확인하고 계산 횟수를 사용하지 않는다. `session.json`의 키를 대화·스크린샷·Git에 붙이지 않는다. 키는 다른 사람과 공유하지 않고 운영자에게서 직접 받는다. 꾸러미의 hash 확인은 전송 중 변경 검출이며 발행자 신원 서명을 대신하지 않는다.

인터넷 없이 설치하려면 신뢰할 수 있는 로컬 dependency wheel 폴더를 준비하고 `python3.12 install.py --venv .venv --offline-wheelhouse /absolute/path/to/wheels`를 사용한다. `PIP_NO_INDEX=1`과 `PIP_FIND_LINKS`로 같은 로컬 폴더를 지정해도 된다. 오프라인 설정에 폴더가 없거나 원격 URL이면 설치 전에 거절한다. 필요한 dependency가 빠져 있으면 공개 registry로 전환하지 않고 실패한다.

2. 합성 예제를 1회 실행하고 결과·독립 검산·평가를 확인한다.

```sh
.venv/bin/python -B main.py --session session.json --input input.json --request-id first-synthetic-run
```

같은 입력·request-id를 다시 보내면 저장된 응답을 받는다. 응답 불명 시 새 ID로 자동 재시도하지 않는다. 입력을 변경한 새 실험에만 새 ID를 사용한다. timeout/unknown은 infeasible 증명이 아니다. 오류·느린 응답이 나오면 코드와 request-id를 운영자에게 전달하고 키나 원문 데이터를 보내지 않는다.

3. Claude Code에서 연결하려면 다음 명령의 두 경로를 실제 절대 경로로 바꾼다. 설정에 키 값은 넣지 않는다.

```sh
claude mcp add --transport stdio ocp-trial -- /absolute/path/.venv/bin/python -B -m ocp_runtime.trial_client --session /absolute/path/session.json mcp
```

Claude Code의 `/mcp`에서 연결을 확인한 뒤, 다음 요청으로 시작한다.

> 먼저 ocp_context 도구로 OCP trial의 기능·입력 조건·요청 template과 schema를 조회해 줘. template의 input에 input.json의 합성 입력을 넣어 검증해 줘. 빠진 값이나 미지원 조건은 추측하지 말고 질문해 줘. request-id는 first-mcp-run으로 사용하고 검증 성공 시 한 번만 계산한 뒤 결과와 평가의 범위를 설명해 줘. 실패하면 새 ID로 재시도하지 마.

리소스를 지원하는 호스트에서는 `ocp://request-guide/0.1.0`을 읽어 같은 안내를 얻을 수 있다. 단순 연결 성공과 LLM의 올바른 판단은 다르다. 실제 모델별 확인 방법은 소스 저장소의 `docs/development/LLM_CONTEXT_VALIDATION.md`를 따른다.

연결 방식은 [Claude Code 공식 MCP 안내](https://code.claude.com/docs/en/mcp)를 따른다. 이 후보의 자동 검사는 공식 Python MCP host를 사용한다. 실제 Claude Code host에서의 최초 연결·승인·계산 시간은 별도 기록한다. Claude 사용에 따른 계정 비용은 운영자의 엔진 시험 예산과 별개다.

시험 한도는 조직별 하루 5회·총 10회, 전체 5개 조직·총 50회, 동시 계산 1개, 키 수명 14일이다. 차량 2~3대·방문 20개 이하·계산 budget 5초 이하의 합성 좌표 입력만 사용한다. 결과 캐시는 24시간 후 삭제하고 사용량·요청 digest·복구 메타데이터는 시험 종료 시 운영자가 전체 폐기한다. 실제 고객·개인·운영 데이터를 입력하지 않는다. 서버는 합성 여부를 자동 증명하지 못한다.

임시 주소는 운영자가 열어둔 시간에만 사용할 수 있다. 주소가 바뀌면 운영자가 새 session 파일을 전달하며 기존 사용량은 유지된다. 시험에서 설치·발급 대기·수동 지원을 포함한 첫 결과 15분과 자기 입력·최소 앱 연결 60분을 측정한다. 자동 검사 통과를 이 목표의 달성으로 계산하지 않는다.

자기 Python/TypeScript 앱, 자기 엔진, 독립 transcript와 오류 복구는 꾸러미의 `DEVELOPER_GUIDE.md`를 따른다. 원본 소스에서는 `docs/users/DEVELOPER_QUICKSTART.md`를 읽는다.
