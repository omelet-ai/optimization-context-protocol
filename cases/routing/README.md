# Routing 검증 사례

현재 design-case는 추상 XY 좌표와 용량에 대한 합성 witness다. 기존 Standard Routing API payload나 실제 도로 거리로 오해하지 않는다. 실제 provider mapping에서 좌표·거리 생성·정수화·비용계수를 맞춰야 한다.

[basic-matrix](basic-matrix.json)는 새 [routing profile 후보](../../spec/profiles/ROUTING_BASIC_0_1.md)의 정수 meter 행렬 사례다. 별도 평가기와 작은 전수 탐색으로 비용 18을 검산하고 입력·구성·상태·평가 오류를 검사한다. H02는 실제 OR-Tools·Omelet API 실행을 뜻하지 않는다. 아래 표는 기존 외부 경로를 포함한 전체 실행 범위다.

| 사례 | 기대 의미 | 현재 상태 |
| --- | --- | --- |
| 작은 정상 입력 | 모든 방문·중량·평가 보존 | H02 독립 평가·oracle 검사 |
| 중량 데이터 누락 | 필요한 필드와 이유 반환 | H02 입력 거절 검사, provider 연결은 후속 |
| 미지원 시간창·weight | 실행 전 명시 거절 | H02 거절 검사, 실제 engine 경로는 후속 |
| timeout·해 미발견 | unknown과 infeasible 구분 | H02 결과 의미 검사, 실제 종료는 후속 |
| 단일 차량 수요 초과 | hard capacity의 경로별 실제 적용 검사 | 실행 미확인, trial 1대 요청 제외 계획 |
| key·quota·만료·회수 | 서버 집행과 소유 범위 보존 | 체험 서비스 구현 예정 |
