# 실제 로컬 Omelet 연결 후보

이 문서는 [좌표 profile](../profiles/ROUTING_COORDINATES_0_1.md)에 대한 로컬 비운영 연결이다. 공개 hosted trial이나 실제 외부 사용자 신원 발급을 주장하지 않는다. [기존 trial 정책](TRIAL_LOCAL_0_1.md)의 SQLite 예약·quota·만료·회수를 실제 엔진 HTTP 경로에 연결한다.

## 신원과 한도

신뢰된 운영자만 `TrialGateway.issue(owner)`로 별도 `ocp_trial_…` key를 발급한다. DB에는 key hash만 저장한다. client는 내부 서비스 token을 받지 않는다. gateway는 key의 owner를 확인한 뒤 owner에서 만든 opaque upstream tenant와 owner+멱등키에서 만든 upstream idempotency ID를 adapter에 전달한다. body·header의 자칭 tenant는 신원으로 사용하지 않는다. 외부 가입·이메일 검증·계약 조직 등록은 미구현이다.

trial HTTP client는 bearer key를 선택적으로 설정하고 `SHA256(UTF-8 request_id)`를 멱등키로 보낸다. request_id가 같고 내용이 다르면 충돌이다. 자동 재전송하지 않으며, 같은 명시 요청의 재호출은 서버의 저장된 응답만 재사용한다. caller deadline은 upstream 종료 증거가 아니다. key를 URL·명령행·로그에 넣지 않는다.

gateway는 기능·크기·solver budget 검증 후 SQLite transaction에서 조직별 일일/누적 호출, 일일/누적/전역 계산시간 예약, 조직별/전역 동시 실행 수를 먼저 예약한다. 키 회전·프로세스 재시작·UTC 날짜 변경으로 누적 quota가 초기화되지 않는다. 추가된 `global_concurrent`도 policy identity에 포함하므로 기존 DB에는 명시적 정책 이행 없이 새 정책을 덮어쓸 수 없다. 허용 여부를 확인한 뒤 이미 진행 중인 작업을 key 회수만으로 소급 취소하지는 않는다.

## 실제 엔진 연결

adapter는 외부 소스를 import하지 않고 Capability Contract HTTP만 호출한다. 시작 시 설정한 catalogDigest와 전체 JSON 문서의 SHA-256을 모두 고정하고 매 solve 전에 확인한다. 지원 검증 범위는 API 1.0, compiler 1.2.0, standard-routing과 명시적으로 선택한 catalog 1.3.0 또는 1.4.0이다. `FoundryBackend(..., catalog_version="1.3.0")`으로 선택하며 기본값은 기존 1.4.0을 유지한다. 두 버전 사이의 자동 선택·전환은 없다. 다른 버전은 명시적 검토 없이 진행하지 않는다. `describe`에는 endpoint·비밀값 없이 이 pin을 선택적 extension으로 기록한다. [검토 근거와 소비자 검증](../../docs/decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md)을 따른다.

Foundry `euclidean`은 이 profile의 구면 Haversine/edge ceil 식에 대응한다. 변환은 좌표·ID·kg·왕복·필수 배정·목적 계수를 보존하며, arbitrary matrix를 좌표로 복원하지 않는다. Foundry의 generated result는 OCP route로 변환한 뒤 비용과 제약을 다시 계산한다. 잘못된 결과는 실패하며 engine 성공 코드만으로 feasible을 만들지 않는다. native solver 버전이 API에 없으므로 `0.0.0-unreported`는 명시적인 미보고 sentinel이고, 실제 버전 추정값이 아니다.

Foundry solver가 초 단위 budget을 받으므로 `floor(time_limit_ms/1000)`초로 내려서 적용한다. 1000 ms 미만은 거절한다. gateway는 요청한 전체 ms를 보수적으로 예약한다. 제출 이후 wall deadline은 요청 solver budget+최대 3000 ms 준비 여유다. deadline이나 불확실한 poll에서 취소를 요청하고 최대 2000 ms 동안 종료를 확인한다. 종료 확인이 실패하거나 submit 응답을 잃어 job ID를 모르면 `EXECUTION_UNCERTAIN`으로 예약과 동시 실행 자리를 유지한다. 실패를 자동 재시도하지 않는다.

이 ms 예약은 통화 청구나 전체 CPU 원가를 의미하지 않는다. 검증 환경은 loopback·외부 통신 차단·합성 입력만 사용한다. 유료 외부 서비스는 실제 금액 한도·권한·원가 규칙을 받은 뒤 별도 검증해야 한다. sync 표면에 공개 job API를 추가하지 않았으며 내부 job ID는 caller에 노출하지 않는다. 운영자 recovery와 실제 외부 trial 운영은 H08/D00/D01의 남은 범위다.
