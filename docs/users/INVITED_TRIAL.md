# OCP 초대 시험 시작하기

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

> OCP trial의 기능을 조회하고 ocp://request-guide/0.1.0 리소스에서 요청 template과 schema를 읽어 줘. template의 input에 input.json의 합성 입력을 넣어 검증해 줘. request-id는 first-mcp-run으로 사용하고 한 번만 계산한 뒤 결과와 평가를 설명해 줘. 실패하면 새 ID로 재시도하지 마.

연결 방식은 [Claude Code 공식 MCP 안내](https://code.claude.com/docs/en/mcp)를 따른다. 이 후보의 자동 검사는 공식 Python MCP host를 사용한다. 실제 Claude Code host에서의 최초 연결·승인·계산 시간은 별도 기록한다. Claude 사용에 따른 계정 비용은 운영자의 엔진 시험 예산과 별개다.

시험 한도는 조직별 하루 5회·총 10회, 전체 5개 조직·총 50회, 동시 계산 1개, 키 수명 14일이다. 차량 2~3대·방문 20개 이하·계산 budget 5초 이하의 합성 좌표 입력만 사용한다. 결과 캐시는 24시간 후 삭제하고 사용량·요청 digest·복구 메타데이터는 시험 종료 시 운영자가 전체 폐기한다. 실제 고객·개인·운영 데이터를 입력하지 않는다. 서버는 합성 여부를 자동 증명하지 못한다.

임시 주소는 운영자가 열어둔 시간에만 사용할 수 있다. 주소가 바뀌면 운영자가 새 session 파일을 전달하며 기존 사용량은 유지된다. 시험에서 설치·발급 대기·수동 지원을 포함한 첫 결과 15분과 자기 입력·최소 앱 연결 60분을 측정한다. 자동 검사 통과를 이 목표의 달성으로 계산하지 않는다.

자기 Python/TypeScript 앱, 자기 엔진, 독립 transcript와 오류 복구는 꾸러미의 `DEVELOPER_GUIDE.md`를 따른다. 원본 소스에서는 `docs/users/DEVELOPER_QUICKSTART.md`를 읽는다.
