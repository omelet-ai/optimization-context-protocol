# Build your own app and engine

## First success from the developer kit

After unpacking the kit, run `python3.12 start.py --venv .local`. This installs
the local dependencies, runs the same app/input with two actual engines, and
independently checks their results and deliberately damaged outputs. No key is
needed. Use `.local/bin/python -B demo.py --diagnostics` for subsequent runs.
See the kit README for prerequisites, offline installation and supported limits.


이 안내의 명령은 **설치 꾸러미를 푼 폴더**에서 실행한다. Python 3.12/macOS arm64, Node 24에서 검증한다. Linux는 별도 검증 대상이며 Windows용 installer는 제공하지 않는다. 회사 저장소·Foundry·API key 없이도 아래 자기 엔진 경로를 사용할 수 있다. Node는 TypeScript를 사용할 때만 필요하다. 현재 artifact는 비공개 후보이고 registry 이름으로 설치하지 않는다.

## 사전 점검

```sh
python3.12 --version
node --version
```

`python3.12: command not found`이면 Python 3.12를 설치하거나 이미 설치된 실행 파일의 절대 경로를 사용한다. `python3 --version`이 3.12라면 아래의 `python3.12`를 `python3`로 바꿀 수 있다. 다른 버전을 자동으로 사용하는 것은 지원하지 않는다. Python 설치 안내: https://www.python.org/downloads/ . Node는 24 이상이 필요하다. 실행 파일을 찾는 문제를 해결한 뒤 시작한다.

## 1. 자기 엔진: 계정·OR-Tools·MCP 없이

새 환경에 기본 SDK와 독립 checker만 설치한다.

```sh
python3.12 -m venv .byo
.byo/bin/python -m pip install --no-compile -c constraints.txt ./ocp_candidate-0.1.0-py3-none-any.whl ./ocp_conformance_candidate-0.1.0-py3-none-any.whl
.byo/bin/python -B byo_library.py basic-input.json --trace own-engine-trace.json
.byo/bin/python -B export_transcript.py --trace own-engine-trace.json --artifact byo_library.py --out own-engine-transcript.json
.byo/bin/python -B -m conformance.runner --bundle own-engine-transcript.json --artifact byo_library.py
```

`byo_library.py`의 `EnumeratingLibrary.solve(problem, time_limit_ms)`가 실제 계산 코드다. 자기 library로 교체할 때 `name`, `version`, `solve`와 반환값 `Outcome(solution, termination, objective)`를 유지한다. 입력은 kg·정수 meter 행렬이다. `solution`은 `{ "routes": [{ "vehicle_id": "v1", "visits": ["a", "b"] }] }` 형태다. 미지원 조건은 validate에서 거절하며 해를 못 찾으면 unknown을 유지한다. 최적성은 별도 증명 없이는 주장하지 않는다.

처음에는 `basic-input.json`을 `my-input.json`으로 복사해 방문 demand와 차량 capacity를 바꿔 실행한다. ID를 바꾸거나 방문을 추가하면 `matrix.node_ids`와 거리 행렬의 행·열도 함께 바꿔야 한다. 같은 입력을 복사 실행한 것은 독립 엔진 개발 실적으로 계산하지 않는다. 작은 library는 방문 6개·차량 3개까지만 지원한다.

trace/transcript는 새 파일만 생성한다. 다시 시험할 때 `own-engine-trace-2.json`처럼 다른 파일명을 사용해 최초 실패를 보존한다. checker의 PASS는 그 요청·응답 의미를 검증하며 엔진 실행·전체 artifact 인증을 대신하지 않는다. `implementation`은 `response.provenance.implementation`에서 복사하며 `engine` ID와 구분한다. artifact에는 실제 검토할 코드/배포 파일을 지정하고 변경되면 hash와 검사를 갱신한다.

## 2. 자기 Python 앱: 로컬 계산 또는 초대 엔진

로컬 reference를 선택하면 위 환경에 OR-Tools extra를 설치한다.

```sh
.byo/bin/python -m pip install --no-compile -c constraints.txt './ocp_candidate-0.1.0-py3-none-any.whl[reference]'
.byo/bin/python -B own_app.py --input basic-input.json --request-id my-local-job-1 --trace my-app-trace.json
```

초대 엔진을 선택하면 README의 installer와 `doctor`를 먼저 실행한 뒤 다음과 같이 호출한다.

```sh
.venv/bin/python -B own_app.py --session session.json --input input.json --request-id my-trial-job-1 --trace my-trial-trace.json
```

`own_app.py`는 discover → requirements → validate → execute → evaluate → 독립 검산의 최소 앱이다. 자기 UI·서버에서는 이 흐름을 함수로 호출하면 된다. 입력 schema는 선택한 profile을 따르며 임의 행렬을 좌표로 자동 변환하지 않는다. 결과 `status`와 metric `status == "evaluated"`를 확인한다. `not_evaluated`의 null을 0으로 바꾸지 않는다. 실패 응답과 infeasible/unknown을 별도로 처리한다.

## 3. 자기 TypeScript 앱

꾸러미의 package.json/tsconfig.json은 Node 24/TypeScript 7의 타입 설정을 포함한다. 공개 의존성 다운로드가 필요하다.

```sh
npm install --no-save --package-lock=false --ignore-scripts --no-audit --no-fund ./ocp-candidate-0.1.0.tgz
npm run build
```

터미널 A에서 로컬 provider를 실행한다.

```sh
.byo/bin/python -B -m ocp_runtime.http_server --port 8765
```

터미널 B에서 실행한다.

```sh
node dist/main.js http://127.0.0.1:8765 basic-input.json --request-id my-ts-job-1
```

다른 입력을 시험할 때에는 `my-ts-job-2`처럼 새 ID를 명시한다. 같은 요청의 재시도는 동일 ID와 동일 입력을 유지한다. 초대 HTTP provider는 별도 `OCP_TRIAL_TOKEN` 환경변수를 사용하며 그 값을 명령 기록·URL·Git에 넣지 않는다. 브라우저 직접 호출용 SDK가 아닌 Node 소비자다.

자기 코드에서는 다음 공개 메서드로 평가까지 진행할 수 있다. `endpoint`와 `input`은 앱에서 받은 값을 사용한다.

```ts
import { Client } from "ocp-candidate";
const client = await Client.connect(endpoint);
const request = client.request(input, undefined, "my-stable-job-id");
const validation = await client.validate(request);
if (!validation.valid) throw new Error("Review validation.issues");
const result = await client.execute(request);
if (result.kind === "failure") throw new Error(result.error.code);
if (result.solution !== null) {
  const evaluation = await client.evaluate(request, result.solution);
  // Preserve evaluation failure, metric.status and null values in your app.
}
```

## 4. MCP: 요청을 추측하지 않고 구성하기

README의 stdio 연결 후 `ocp_context()` 도구를 먼저 호출한다. 리소스를 지원하는 호스트에서는 `ocp://request-guide/0.1.0`을 읽어 같은 안내를 얻을 수 있다. Core request schema, 선택 profile의 input schema, provider의 기본 configuration·budget을 담은 request template이 제공된다. template의 `input`을 자기 합성 입력으로, `request_id`를 명시한 작업 ID로 바꾼다. 빠진 입력을 추측하지 말고 질문한다. validate가 valid=true일 때 execute하고 non-null solution만 evaluate한다. 컨텍스트 조회는 계산을 수행하지 않는다. 모르는 profile에서 input_schema가 null이면 해당 provider 문서를 먼저 확인한다.

공식 MCP Python host 검증은 실제 Claude Code host의 승인 화면·도구 선택 검증을 대신하지 않는다. 서버 주소/권한/pin을 임의로 바꾸거나 오류 후 새 ID로 자동 재시도하지 않는다.

## 5. 실패에서 복구하기

| 진단 | 다음 행동 |
| --- | --- |
| PYTHON_VERSION_UNSUPPORTED | Python 3.12 실행 파일 경로를 확인하고 installer --check를 다시 실행 |
| ENVIRONMENT_EXISTS | 기존 환경으로 doctor를 실행하거나 새 --venv 경로 선택 |
| KIT_CHECKSUM_MISMATCH | 새 꾸러미를 다시 풀기. manifest를 수정하지 않기 |
| INVITATION_NOT_FOUND / INVITATION_JSON_INVALID | 정확한 session 경로 확인 또는 발급자에게 새 파일 요청 |
| INVITATION_PERMISSIONS | chmod 600 session.json 후 doctor 재실행 |
| UNAUTHORIZED / TRIAL_EXPIRED | 발급자에게 키 상태·시험 종료 시각 문의 |
| CATALOG_CHANGED | 중단하고 검토된 새 session 요청. pin을 스스로 덮어쓰지 않기 |
| IDEMPOTENCY_CONFLICT | 기존 작업이면 원래 입력 복원. 다른 작업이면 새 request ID 선택 |
| TRANSPORT_UNCERTAIN | 요청 ID 보존. 연결·시험 시간 확인 후 발급자에게 오류 코드 문의 |

잘못된 입력은 JSON 중복 키·NaN·단위·필수 필드부터 확인한다. 키·원문 데이터 대신 오류 코드와 request ID만 공유한다. 유료 서비스나 공개 배포를 자동으로 만들지 않는다.
