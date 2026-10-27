# Routing basic 0.1 계약 후보

상태: 공개 개발자 프리뷰 계약 `routing.basic@0.1.0`. [Core](../core/CORE_0_1.md)와 [sync](../execution/SYNC_0_1.md)를 소비한다. [입력 schema](../schemas/routing-input-0.1.schema.json), [해 schema](../schemas/routing-solution-0.1.schema.json), [구성 schema](../schemas/routing-configuration-0.1.schema.json)가 이 후보의 구조 정본이다.

## 입력과 비용

depot 하나, 차량 1~16대, 필수 방문 1~64개를 지원 범위로 정의한다. 모든 차량은 같은 depot에서 출발·복귀하며 단일 trip이다. 차량 사용 여부는 선택이며 사용하지 않는 차량도 빈 방문 목록으로 결과에 포함한다. 차량별 시작점·종점, 시간창·근무시간·skills·다회전·미배정·soft 제약은 지원하지 않는다.

각 방문은 음이 아닌 정수 kg 수요, 각 차량은 양의 정수 kg 용량이다. `load_unit`은 kg다. matrix는 depot와 모든 visit ID를 정확히 한 번 포함하고 정방형이어야 한다. 대각 원소는 0, 원소는 0~1,000,000,000의 정수 meter다. 비대칭 거리와 삼각 부등식을 만족하지 않는 행렬도 그대로 사용한다. 도중에 다른 점을 경유하는 최단 경로로 행렬을 다시 계산하지 않는다.

`model=explicit_matrix`, `rounding=none`이다. 이 profile 안에서 좌표 변환·반올림·정수화하지 않는다. 외부 입력에서 matrix를 만드는 별도 adapter는 거리식·단위·rounding·version을 명시하고 검증해야 한다. 이 정의가 Omelet API의 euclidean 좌표 처리와 같다는 뜻은 아니다. 실제 교집합을 확인하기 전에는 두 엔진의 품질을 비교하지 않는다.

## 구성과 불변조건

목적은 `minimize_total_route_cost` 하나, weight는 1이다. parameters는 거리 계수 1·시간 계수 0·고정비 0으로 고정한다. 다른 값·추가 목적·미지원 parameter는 `UNSUPPORTED_CONFIGURATION`으로 거절한다. 선택 가능한 hard 제약은 `weight_capacity`이고 이 후보에서는 항상 켠다. 모든 방문을 정확히 한 번 배정하는 `all_visits_once`와 depot 왕복은 profile 불변조건이며 사용자가 해제할 수 없다.

차량 route의 비용은 depot→방문 순서→depot의 각 행렬 원소 합이다. 비어 있는 route의 비용은 0이다. 목적값은 전체 route 비용 합이며 단위는 meter다. 고정비·시간·정규화·importance의 숨은 효과가 없다. 이름에 cost가 있어도 이 profile에서 통화 비용을 뜻하지 않는다.

feasible 판정에는 모든 방문 정확히 한 번, 알려진 ID만 사용, 각 차량의 수요 합 ≤ 용량, 차량별 하나의 route, depot 출발·복귀가 필요하다. invalid input, 미지원 구성, feasible solution, optimal proof를 구분한다.

## 독립 평가와 증명

`routing.basic.total_distance.v1`은 위 전체 거리 합이다. `routing.basic.weight_capacity.v1`의 violation은 차량별 `max(0, load-capacity)`의 합(kg)이다. `routing.basic.all_visits_once.v1`의 violation은 방문별 `abs(배정 횟수-1)` 합(count)이다. 위반값 0만 satisfied=true다. 알 수 없는 방문·차량, 중복 차량 route 또는 잘못된 해 구조는 평가 오류이며 수치를 0으로 반환하지 않는다.

result에는 optimized metric 하나와 enforced constraint 평가 두 개를 반환한다. 해가 없을 때 평가를 생략하거나 not_evaluated/null/사유로 명시한다. `unknown` 또는 증명 없는 휴리스틱 실패를 `infeasible`로 바꾸지 않는다.

검사기는 작은 사례에서 engine과 독립적인 모든 차량 배정·방문 순서 열거로 최적값을 검산한다. oracle 한도는 방문 7개·차량 3대이며 초과하면 `ORACLE_SCOPE_EXCEEDED`다. production solve에 이 oracle을 import하지 않는다. 큰 문제의 feasible 검사와 작은 문제의 최적성 검산을 구분한다.

infeasible의 허용 근거는 필수 총수요가 총용량 초과, 한 방문 수요가 모든 차량 용량 초과, 또는 위 한도 안의 완전 열거다. `optimal`은 한도 안의 완전 열거로 최적값을 재검증할 수 있는 경우에만 이 후보에서 확인한다. solver의 성공 코드·제한 시간 종료·검색 실패를 증명으로 쓰지 않는다.

해석적 증명의 `evidence`도 입력에서 다시 계산한 값과 일치해야 한다. `total-demand-exceeds-total-capacity`는 `total_demand`·`total_capacity`, `individual-demand-exceeds-all-capacities`는 `maximum_demand`·`maximum_capacity`를 정수 kg 값으로 제공한다. 누락·다른 값·boolean·실수는 거절한다. 불가능하다는 결론이 맞아도 설명에 사용한 숫자가 틀리면 그 증명 응답은 통과하지 않는다.

## 사례와 호환 경계

[수작업 행렬 사례](../../cases/routing/basic-matrix.json)의 route 비용은 6과 12, 총 18이다. 독립 oracle도 18을 확인한다. [기존 greedy 반례](../../cases/failure-semantics/greedy-feasible.json)는 용량 6 두 개·수요 3,3,2,2,2의 실제 feasible 배정이 존재함을 확인한다. 합성 입력이며 기존 Standard API payload가 아니다.

기존 routing design-case의 XY 좌표·witness는 보존하고 새 wire payload로 자동 해석하지 않는다. trial은 실제 provider와 환경 정책을 더 좁혀 적용한다. 기존 API의 단일 차량 capacity 경로가 검증되기 전 trial 1대 요청 제외 원칙은 유지한다. 이 profile의 local 차량 1대 지원이 그 외부 경로 검증을 대신하지 않는다.
