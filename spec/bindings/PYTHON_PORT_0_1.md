# Python 동기 adapter port 후보

`ocp_candidate.Adapter`는 transport와 독립적인 describe, requirements, validate, execute, evaluate 경계를 정의한다. Client는 capability 선언에서 ID·profile·defaults를 읽고 명시적인 Core request를 만든다. 도메인 ID에 따른 분기나 자동 engine fallback은 하지 않는다.

| 메서드 | 입력 | 출력과 책임 |
| --- | --- | --- |
| describe | 없음 | capability. 실제 지원·기본값·한계의 정본 |
| requirements | 명시 configuration | requirements 또는 failure. 선택을 변경하지 않음 |
| validate | Core request | validation. solve하지 않음 |
| execute | Core request | result 또는 failure. 직접 호출에도 재검증 |
| evaluate | Core request, profile solution | evaluation 또는 failure. 평가와 최적성 증명 구분 |

Client는 caller 입력과 요청을 복사하고 응답의 request ID·capability/profile/execution 버전·effective configuration을 대조한다. 원격 재시도·job·cancel은 이 sync port에 포함하지 않는다. Core 구조 검사만으로 임의 엔진의 수학적 적합성을 인증하지 않는다. 새 provider는 독립 conformance를 통과해야 한다.

현재 routing adapter는 공개 OR-Tools library의 명시 행렬·hard capacity를 실제 호출한다. backend 구현은 `name`, `version`, `solve(problem, time_limit_ms)`를 제공하고 `Outcome(solution, termination, objective)`를 반환한다. 같은 profile 의미를 지원하는 backend만 연결한다. 이 callback 구조만 구현했다고 임의 solver를 호환으로 인정하지 않는다.

provider는 단위·행렬·ID·구성·예산을 확인하고 결과의 배정·capacity·비용을 다시 검사한다. 파악 가능한 총수요·단일 방문 용량 불가능성은 명시적인 분석 증거로 처리한다. 실제 solver를 호출하지 않은 이 경로는 provenance 제한에 표시한다. 검색 미발견은 unknown이며, OR-Tools가 해를 찾았다는 사실만으로 optimal을 반환하지 않는다.

OR-Tools 호출 예산은 solver search 시간이다. validation·model 준비·직렬화·전체 프로세스 시간을 보장하지 않는다. 1~5000ms를 수용하고 초과 요청을 거절한다. 직접 HTTP·REST wrapping과 TypeScript client는 H06에서 별도로 구현·검증한다.

구현 소유 경로는 `sdk/python`과 `adapters/python`이다. [build 도구](../../tools/build_candidate.py)가 새 코드와 canonical schema를 private wheel로 묶는다. 설치된 runtime은 workspace·snapshot·conformance를 import하지 않는다. 이 후보의 공개 namespace·라이선스·게시 승인은 미정이다.

실제 library 동작은 [OR-Tools capacity 문서](https://developers.google.com/optimization/routing/cvrp)와 [검색 상태·시간 제한 문서](https://developers.google.com/optimization/routing/routing_options)를 참고해 작성했다. 원본 예제 코드를 복사하지 않았으며 검증 dependency는 `ortools==9.15.6755`다.
