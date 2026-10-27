# Start with the path you need

현재는 Apache-2.0 공개 개발자 프리뷰다. 설명 사이트도 공개되었으며 Omelet trial 발급·운영은 별도다. 공개 registry에 존재한다고 가정해 `pip install ocp-candidate`를 실행하지 않는다. 검증한 로컬 wheel/tarball을 사용한다. Python 3.12/macOS arm64, Node 24에서 검사했다.

## Try Omelet

권장 첫 체험은 제한된 실제 Omelet Routing Engine이다. 승인된 로컬 비운영 환경에서는 [좌표 profile](../../spec/profiles/ROUTING_COORDINATES_0_1.md)의 실제 엔진을 별도 trial key와 한도 정책으로 연결한다. 운영자가 endpoint와 안전한 key 전달 경로를 제공한 경우 App A의 `--endpoint` 또는 App B의 endpoint 인자와 `OCP_TRIAL_TOKEN` 환경변수로 사용한다. key 값을 명령행·URL·로그에 넣지 않는다. 공개 가입·외부 사용자 운영은 아직 제공하지 않는다. 키 만료·한도 초과 시 다른 엔진으로 자동 전환하지 않는다. 상세 범위는 [로컬 연결 계약](../../spec/environments/OMELET_LOCAL_TRIAL_0_1.md)을 따른다.

## Run locally

개발자가 제공한 `ocp_candidate-0.1.0-py3-none-any.whl`을 새 가상환경에 설치한다. 공개 PyPI 의존성은 wheel metadata에 고정돼 있다.

```sh
python3.12 -m venv /tmp/ocp-example
/tmp/ocp-example/bin/python -m pip install './ocp_candidate-0.1.0-py3-none-any.whl[reference]'
/tmp/ocp-example/bin/python -B examples/app-a/main.py --input my-input.json
```

첫 입력은 `cases/routing/basic-matrix.json`의 `input` 객체를 JSON 파일로 저장한다. 직접 입력할 때 depot·visit/vehicle ID·kg demand/capacity·방향별 정수 meter 행렬을 제공한다. 행/열은 node_ids 순서이며 좌표 변환과 반올림은 없다. 결과의 kind/status, metrics의 evaluated 여부와 단위, constraints를 확인한다. `feasible`은 최적성 증명이 아니며 `unknown`은 불가능 판정이 아니다.

선택 HTTP: `python -B -m ocp_runtime.http_server --port 8765`. App B는 npm tarball을 설치하고 `main.ts`를 컴파일한 다음 `node dist/main.js http://127.0.0.1:8765 my-input.json --request-id my-job-1`으로 실행한다. HTTP 서버는 loopback 전용이다.

선택 MCP: wheel의 `[reference,mcp]`를 설치하고 host의 stdio command를 해당 환경의 Python, args를 `-I -B -m ocp_runtime.mcp_server`로 설정한다. 검증한 host는 공식 MCP Python Client 2.3.0이다. Claude Code 첫 공식 데모는 실제 trial 연결과 함께 별도로 검증할 예정이다. global 설정을 자동 변경하지 않는다.

## Bring your engine

wheel 기본 설치만으로 `python authoring/byo_library.py my-input.json`을 실행할 수 있다. 이 예제는 작은 실제 순열 탐색 library이며 OR-Tools/Omelet을 호출하지 않는다. 방문 6개·차량 3개 범위에서 같은 routing.basic을 사용한다. 자기 library·SDK는 adapter port로, 기존 OCP HTTP 구현은 HTTPAdapter로 연결한다. 상세 범위와 거절 원칙은 [authoring](../../authoring/README.md)에 있다.

독립 checker wheel은 `python -B -m conformance.runner --bundle transcript.json --artifact candidate.whl`로 실행한다. bundle 형식과 범위는 [conformance](../../conformance/README.md)를 따른다. 잘못된 fixture가 통과하면 제품 완료로 보고하지 말고 재현 사례를 추가한다.

15분 첫 실행·60분 앱 통합은 실제 외부 개발자에게 측정할 목표다. 위 자동 검사의 소요시간을 사용자 성공률로 바꾸지 않는다.

좌표 입력은 `cases/routing/coordinates.json`의 `input`을 별도 JSON 파일로 저장하고 App A에 `--profile coordinates`를 추가한다. 좌표 모드도 계정 없이 OR-Tools로 실행할 수 있다. 기본 모드의 임의 거리행렬 입력과 구분한다.

설치 꾸러미의 복사 실행 가능한 앱·엔진·transcript 명령은 [개발자 시작 안내](DEVELOPER_QUICKSTART.md), 원본 소스 빌드는 [빌드 안내](../development/BUILD_FROM_SOURCE.md)를 따른다.
