# Bring your engine

`byo_library.py`는 실제 작은 순열 탐색 library를 routing.basic adapter에 연결한 독립 실행 예제다. 기본 Python wheel만 설치하면 되며 OR-Tools·Omelet 계정·Foundry가 필요하지 않다. 입력은 App A와 같다.

```sh
python -B byo_library.py my-input.json
```

방문 6개/차량 3개까지 지원하고 초과 입력은 solve 전에 거절한다. 명시한 실행 예산이 끝나면 발견한 해는 feasible, 해가 없으면 unknown이다. 최적성 증명은 발행하지 않는다. 학습용 작은 library이며 실제 대형 엔진 성능을 대표하지 않는다.

자기 library/SDK의 입력·해를 변환할 때 objective, weight, hard 제약, 단위와 비용을 보존한다. `describe/requirements/validate/execute/evaluate` port를 구현하고 unsupported 조합을 거절한다. 기존 HTTP API가 이 후보 binding을 이미 제공하면 `ocp_candidate.http_adapter.HTTPAdapter`로 연결한다. 다른 REST API에는 명시적인 mapping과 별도 검증이 필요하다.

선택적 서버 pair는 같은 adapter에 `ocp_runtime.http_server.create_server` 또는 `ocp_runtime.mcp_server.create_mcp`를 연결한다. stdio/HTTP와 domain 의미를 분리한다. SDK만 사용하는 앱에 서버나 내부 OIP를 요구하지 않는다. 직접 작성한 engine 결과는 독립 conformance로 검사하고 실제 실행 증거를 별도로 남긴다.

## 실제 transcript 만들기

독립 checker wheel도 설치하고 다음 명령을 실행한다. 파일명은 재실행 때 새 이름을 선택한다.

```sh
python -B byo_library.py my-input.json --trace trace.json
python -B export_transcript.py --trace trace.json --artifact byo_library.py --out transcript.json
python -B -m conformance.runner --bundle transcript.json --artifact byo_library.py
```

implementation은 결과의 provenance.implementation이며 engine ID가 아니다. export 도구가 이 정체성과 artifact hash를 실제 trace에서 복사한다. 다른 코드로 바꾸면 새 trace/hash로 검사한다. failure는 종료 코드 2다. 전체 설치와 자기 앱 연결은 [시작 안내](../docs/users/DEVELOPER_QUICKSTART.md)를 따른다.
