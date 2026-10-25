# assignment.fixture 0.1.0

상태: 도메인 분리 검사용 비공개 fixture. production 실행 profile로 권고하거나 solver 구현을 제공하지 않는다.

입력은 고유한 items/workers 목록과 item 행·worker 열의 0 이상 정수 비용 행렬이다. 각각 1~8개, 비용은 10^9 이하 cost_unit이다. 각 item을 서로 다른 worker 한 명에 배정하고 비용 합을 최소화한다. configuration은 cost weight=1, unique_assignment, 빈 parameters다.

`spec/schemas/assignment-fixture-input-0.1.schema.json`과 `assignment-fixture-solution-0.1.schema.json`이 구조를 정한다. `conformance/assignment.py`는 행렬 크기, 모든 item의 정확히 한 번 배정, worker 중복 금지, 비용·제약 측정의 일치를 독립 확인한다. 현재 suite는 feasible witness만 검증하며 optimal/infeasible claim을 인증하지 않는다.

정상·거부 사례는 H05에서 검사한다. Core 변경 없이 domain registry에 checker를 추가하며 Routing·Omelet·endpoint·tenant 필드는 필수가 아니다.
