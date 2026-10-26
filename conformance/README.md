# Independent conformance candidate

Core의 구조·상태 의미, `routing.basic@0.1.0` 결과, 두 번째 도메인 `assignment.fixture@0.1.0`의 합성 witness를 독립 검사한다. runtime SDK나 solver 코드를 import하지 않는다.

```sh
python -B -m conformance.runner --bundle transcript.json --artifact candidate.whl
```

bundle은 `artifact_sha256`, `implementation: {id, version}`, 비어 있지 않은 `cases: [{id, request, response}]`로 구성한다. case ID는 유일해야 한다. artifact 파일 hash와 bundle을 대조하고 Core conformance 보고서를 반환한다. 각 case의 상태와 미시험 범위를 함께 읽는다. 오류 종료 코드는 1이다.

이는 **제출한 요청·응답의 의미 검사**다. 해당 artifact가 응답을 생성했는지, 다른 엔진·profile·binding이 맞는지, 공개 가능한지를 증명하지 않는다. 실제 실행 근거는 H03/H04/H06/H08에서 별도로 수집한다. 검사하지 않은 항목은 NOT_TESTED다. 알 수 없는 profile은 거절한다.

잘못된 비용·단위·용량·방문 누락·목적/제약 추가·가중치 drift·거짓 infeasible/optimal·timeout·null 변환을 고의로 주입해 검출을 확인한다. Routing 작은 oracle는 방문 7개/차량 3대까지만 완전 탐색한다. 실환경의 모든 입력에 대한 최적성을 주장하지 않는다.

배정 fixture의 입력·해 schema, capability·requirements·result는 `cases/assignment/fixture.json`에 있다. item마다 서로 다른 worker 하나를 배정하고 주어진 정수 비용을 합한다. 합성 기대값은 5이며 실제 assignment solver를 호출한 결과가 아니다. 이 fixture는 Routing 전용 필드 없이 같은 Core 계약을 사용하는 범위를 검증한다.

처음 transcript를 만들 때는 [BYO의 실행·내보내기 예제](../authoring/README.md)를 사용한다. implementation에는 response.provenance.implementation을 넣는다. provenance.engine과 혼동하지 않는다. metric은 evaluated boolean이 아니라 status: evaluated/not_evaluated와 value 필드를 갖는다. artifact에는 실제 검토 대상 파일을 지정한다. exporter가 bundle을 만들었다는 사실만으로 PASS가 아니며 runner를 실행해야 한다.
