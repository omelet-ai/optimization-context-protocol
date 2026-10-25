# Bring your engine

`byo_library.py`는 실제 작은 순열 탐색 library를 routing.basic adapter에 연결한 독립 실행 예제다. 기본 Python wheel만 설치하면 되며 OR-Tools·Omelet 계정·Foundry가 필요하지 않다. 입력은 App A와 같다.

```sh
python -B byo_library.py my-input.json
```

방문 6개/차량 3개까지 지원하고 초과 입력은 solve 전에 거절한다. 명시한 실행 예산이 끝나면 발견한 해는 feasible, 해가 없으면 unknown이다. 최적성 증명은 발행하지 않는다. 학습용 작은 library이며 실제 대형 엔진 성능을 대표하지 않는다.

자기 library/SDK의 입력·해를 변환할 때 objective, weight, hard 제약, 단위와 비용을 보존한다. `describe/requirements/validate/execute/evaluate` port를 구현하고 unsupported 조합을 거절한다. 기존 HTTP API가 이 후보 binding을 이미 제공하면 `ocp_candidate.http_adapter.HTTPAdapter`로 연결한다. 다른 REST API에는 명시적인 mapping과 별도 검증이 필요하다.

선택적 서버 pair는 같은 adapter에 `ocp_runtime.http_server.create_server` 또는 `ocp_runtime.mcp_server.create_mcp`를 연결한다. stdio/HTTP와 domain 의미를 분리한다. SDK만 사용하는 앱에 서버나 내부 OIP를 요구하지 않는다. 직접 작성한 engine 결과는 독립 conformance로 검사하고 실제 실행 증거를 별도로 남긴다.
