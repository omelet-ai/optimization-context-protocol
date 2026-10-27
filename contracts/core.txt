# OCP Core 0.1 계약 후보

상태: 비공개 기술 후보. 이 프로젝트 안의 H01 구현·검증 기준이며 공개 승인이나 공식 namespace 확정이 아니다. JSON 교환 버전은 `0.1.0`, schema ID는 임시 `urn:ocp:candidate:core:0.1.0`이다. 구조 정본은 [schema](../schemas/core-0.1.schema.json)다.

## 목적과 소유 경계

Core는 capability·구성·요구사항·실행·결과·실패·평가·검사 보고의 공통 의미를 정의한다. domain profile은 입력·해·목적식·제약·단위·평가 정의를, execution profile은 동기 또는 job 약속을 소유한다. binding은 전달 방식, environment profile은 신뢰·격리·수명·복구를 소유한다. UI·사람 승인·고객 업무·과금은 Application 또는 서비스 정책이다.

`input`과 `solution`은 profile 소유 객체다. Core에 route·vehicle·hospital 같은 entity를 넣지 않는다. 최소 local 구현에 계정·endpoint·HTTP·MCP·DB·OIP·state key를 요구하지 않는다. Core 검증만 통과한 payload는 domain 검증이나 실행 완료가 아니다.

## 교환 형식과 버전

JSON Schema Draft 2020-12를 사용한다. 모든 envelope는 `core_version`, `kind`를 가진다. 모르는 envelope 필드는 거절한다. 중복 JSON key, NaN·Infinity와 비 JSON 값은 거절한다. JSON 정수는 언어 간 손실 방지를 위해 절댓값 `2^53-1` 이내로 제한한다. 소수의 허용 오차·반올림은 profile이 정한다.

capability, domain/execution profile, implementation, engine과 suite는 각각 `{id, version}`으로 식별한다. `latest`나 버전 없는 참조는 허용하지 않는다. 제공자는 실행 전 요청의 capability·profile·버전을 자신이 실제 지원하는 선언과 대조한다. 전송 연결이나 대화 기록으로 누락된 실행 의미를 추측하지 않는다.

이 후보에서는 exact version match를 사용한다. 같은 major 또는 patch라는 이유로 자동 호환 처리하지 않는다. 목적식·제약·단위·반올림·가중치·필수 입력·평가 의미 변화는 breaking 변경으로 판정하고 profile·consumer migration을 기록한다. 향후 호환 범위는 명시적인 검증된 조합으로만 넓힌다.

## 메시지와 책임

| kind | 필수 의미 | 실행 책임 |
| --- | --- | --- |
| capability | provider/version, profile/binding/environment, 목적·제약·configuration schema·입력/해 schema ID·defaults·한계 | 실제 실행 의미를 책임지는 provider가 선언 |
| request | request ID, capability/domain/execution 버전, 명시 configuration, inline input, time budget | provider 경계에서 전체 검증 후 실행 |
| requirements | effective configuration, 필요한 JSON pointer·이유·단위, input schema ID | 선택에 따른 요구를 계산. 데이터 사전 전체와 구분 |
| validation | request ID, valid, issues | 입력·선택 검사이며 solve·feasibility 증명이 아님 |
| result | 상태·종료 이유·해·proof·평가·effective configuration·provenance | 실제 engine 결과와 근거를 보존 |
| failure | request ID 또는 null, code·message·retryable·issues | 해 결과와 구분. 메시지에 내부 secret·traceback을 노출하지 않음 |
| evaluation | request ID·capability/domain, metric·constraint 평가, evaluator·한계 | engine 보고와 독립 재계산을 구분 |
| conformance | implementation·artifact SHA-256·suite·profiles·검사별 상태와 이유 | 검사 범위만 보고. 고객 수락이나 공개 권리를 주장하지 않음 |

capability의 `configuration_schema`는 독립 JSON Schema이고 내부 fragment 참조만 허용한다. 문서에서 임의 URL을 따라 schema를 내려받지 않는다. input/solution schema ID는 설치된 profile registry에서 해석하며, 인터넷 조회 권한이 아니다. defaults는 선언된 configuration schema를 만족해야 한다.

`configuration`은 objectives의 ID·weight, constraints ID 목록, profile 소유 parameters로 구성한다. 여러 objective를 나열한 것은 다목적 실행 약속이 아니다. 실제 허용 조합·가중치·parameter 값은 provider의 configuration schema와 profile 검사로 확인한다. 선택을 무시하거나 hard 제약을 가중치로 완화하지 않는다. 누락된 기본값은 requirements에서 effective configuration으로 명시하고 실행 요청에 확정해 넣는다.

## 결과와 평가 의미

`feasible`은 해당 profile의 hard 조건을 만족하는 해가 있다는 뜻이고 최적성 주장이 아니다. `optimal`은 feasible 해와 최적성 증거를 모두 요구한다. `infeasible`은 해가 없다는 증거를 요구한다. `unknown`은 해나 불가능성을 확인하지 못한 상태다. unknown·infeasible에는 solution을 null로 둔다.

종료 이유는 `completed`, `time_limit`, `cancelled`, `search_exhausted`다. time_limit·cancelled는 optimal/infeasible 근거가 될 수 없다. 시간 종료 때 유효한 해를 확보했다면 feasible과 time_limit을 함께 반환할 수 있다. `search_exhausted`도 그 자체로 증명이 아니다. proof의 method·scope·evidence와 profile별 검증이 추가로 필요하다.

schema가 proof의 존재를 검사해도 수학적 증명을 검증한 것은 아니다. profile/adapter가 증거를 확인할 수 없으면 optimal/infeasible로 승격하지 않는다. runtime 장애나 미지원 요청에는 failure를 반환한다. timeout 자체를 infeasible로 mapping하지 않는다.

objective는 `optimized/reported`, constraint는 `enforced/evaluated`를 구분한다. 평가에는 정의·단위·출처(`engine/independent`)와 평가 상태가 있다. `not_evaluated`는 value/violation/satisfied를 null로 두고 이유를 요구한다. null을 0·충족으로 변환하지 않는다. constraint의 violation 0이면 satisfied=true, 양수면 false다. profile이 위반 수식과 hard/soft 관계를 정한다.

request ID는 상관관계 식별자이며 인증·입력 hash가 아니다. provider는 요청을 변경 불가능한 실행 단위로 취급하고 응답에 같은 ID·참조 버전·effective configuration을 연결한다. result의 provenance request ID도 일치해야 한다. client는 원 요청과 비교하고 evaluator는 원 입력과 실제 해를 함께 받는다. public content digest는 이 Core 후보의 필수사항이 아니다. 도입할 때 canonicalization·범위·알고리즘을 별도 정의한다. 기존 Omelet opaque digest를 새 내용에 재사용하지 않는다.

## 확장과 오류

확장은 `{id, version, required, value}` 목록으로 표현한다. ID 중복을 거절한다. 모르는 `required=true` 확장은 실행 전에 `UNSUPPORTED_EXTENSION`으로 거절한다. optional 확장은 표시 힌트 등 실행 의미를 바꾸지 않는 정보만 담는다. 목적·제약·데이터·버전을 바꾸는 의미를 optional로 숨기는 것은 부적합이다. v0.1 Core 자체가 등록한 필수 확장은 없다.

기본 오류는 `INVALID_REQUEST`, `INVALID_DATA`, `VERSION_MISMATCH`, `UNSUPPORTED_CONFIGURATION`, `UNSUPPORTED_EXECUTION`, `UNSUPPORTED_EXTENSION`, `EXECUTION_ERROR`, `DEADLINE_EXCEEDED`다. 원격 환경은 `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `LIMIT_EXCEEDED`를 추가할 수 있다. 알 수 없는 오류 code도 실패로 보존한다. retryable은 무조건 재실행하거나 다른 엔진으로 바꾸라는 지시가 아니다. 자동 재시도·멱등성은 선언한 execution/environment 계약이 있을 때만 적용한다.

## 검증 범위와 출처

[Core fixtures](../../cases/core/messages.json)는 합성 예제이며 실제 solver 실행 결과가 아니다. H01은 schema·오류·상태·확장·버전 형태와 독립성을 검증한다. H02 이후 domain 검증과 H03 이후 provider/client 비교가 별도로 필요하다. 공개 권리·라이선스와 외부 환경은 아직 미승인이다.

설계는 새로 작성했으며 Foundry 구현의 코드를 runtime으로 가져오지 않았다. 내부 계약 mapping과 개발 요구 추적은 별도 개발 자료로 관리하며 이 규격의 사용 조건이 아니다. Schema 방언은 [JSON Schema 공식 Core 문서](https://json-schema.org/draft/2020-12/json-schema-core), 검사 API는 [python-jsonschema 공식 문서](https://python-jsonschema.readthedocs.io/en/stable/validate/)를 기준으로 고정했다.
