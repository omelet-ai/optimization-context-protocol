# Routing coordinates 0.1 계약 후보

비공개 제안 `routing.coordinates@0.1.0`. [Core](../core/CORE_0_1.md), [sync](../execution/SYNC_0_1.md), [좌표 입력 schema](../schemas/routing-coordinates-input-0.1.schema.json), [구성 schema](../schemas/routing-configuration-0.1.schema.json), [해 schema](../schemas/routing-solution-0.1.schema.json)를 사용한다. 기존 `routing.basic@0.1.0`의 명시적 방향별 행렬 의미는 변경하지 않는다. 이 profile은 특정 엔진·endpoint·OIP·계정을 요구하지 않는다.

## 의미와 범위

입력은 한 depot, 차량 2~16대, 방문 1~64개다. depot와 visit은 `location.latitude`와 `location.longitude`를 도 단위 JSON number로 제공한다. 위도 범위는 [-85,85], 경도는 [-180,180]이며 NaN·Infinity·boolean은 거절한다. depot/visit ID는 전체에서, 차량 ID는 차량 집합에서 유일해야 한다. 명시적 행렬·고도·도로망·geocoding은 이 profile에 넣지 않는다.

`distance`는 `{model: "haversine", earth_radius_m: 6371000, rounding: "ceil", unit: "meter"}`다. 위·경도를 radian으로 변환한 뒤 `h=sin²(Δlatitude/2)+cos(latitude_a)cos(latitude_b)sin²(Δlongitude/2)`, `d=2R atan2(sqrt(h),sqrt(1-h))`로 구면 대권거리를 구한다. 부동소수 오차로 h가 [0,1] 밖에 있을 때 그 구간으로 제한한다. 각 edge를 미터 정수로 올림하며, 합산한 뒤 반올림하지 않는다. 동일 좌표의 거리는 0이다. road 거리나 WGS84 타원체 측지거리와 같다는 주장은 하지 않는다. 서로 다른 구현의 정수화가 경계에서 달라지면 결과를 거절하며 허용 오차로 다른 정수 비용을 수용하지 않는다.

수요는 음이 아닌 정수 kg, 용량은 양의 정수 kg이다. depot 왕복·단일 trip·모든 방문 정확히 한 번·weight_capacity가 필수다. 사용하지 않는 차량도 빈 route를 반환한다. 목적은 전체 거리 최소화 하나, weight=1, 거리 계수=1, 시간 계수=0, 고정비=0이다. 다른 목적·시간창·skills·soft 제약·미배정·다회전은 거절한다. 구성 구조는 basic과 공유하지만 input과 평가 정의는 다른 profile이다.

`routing.coordinates.total_distance.v1`은 위 edge 합, `.weight_capacity.v1`은 차량별 양의 초과 kg 합, `.all_visits_once.v1`은 방문별 배정 횟수와 1의 차이 절댓값 합이다. `feasible`, `unknown`, 증명된 `infeasible` 및 null 의미는 [basic](ROUTING_BASIC_0_1.md)의 상태 규칙을 그대로 적용한다. solver의 no-solution은 infeasible 증명이 아니다.

## 구현과 검증

로컬 library adapter는 이 입력으로 명시적 행렬을 생성하고 OR-Tools를 호출한다. 독립 conformance는 adapter를 import하지 않고 별도 scalar 거리식·평가·전수 탐색으로 검증한다. [합성 사례](../../cases/routing/coordinates.json)는 차량 2대·방문 4개, 총 거리 11358 m다. 극단 좌표·미소 거리·단위/정수화 drift·가짜 infeasible·누락 방문·잘못된 비용은 별도로 검사한다.

공통 solver budget 범위는 1000~5000 ms다. 실제 엔진의 적용 단위와 전체 호출 deadline은 구현 제한에 선언한다. Omelet 연결의 검증 범위는 차량 2~3대·방문 20개 이하며 local reference가 더 큰 입력을 받는다고 Omelet도 받는 것으로 추정하지 않는다.

새 profile 추가는 기존 Core/basic 메시지·버전을 변경하지 않는다. private package 0.1.0은 아직 동결되지 않은 후보이고 exact artifact hash로 구별한다. 공개 전 배포 버전 동결과 권리 검토는 별도다. profile 변경은 새 버전/호환 검증이 필요하다.
