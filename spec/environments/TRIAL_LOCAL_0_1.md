# Trial policy local candidate 0.1.0

이는 H07의 비공개 정책 구현이며 실제 Omelet trial 서비스가 아니다. 현재 실행 provider는 OR-Tools reference다. 신원 발급자·원 API catalog mapping·서비스 토큰·상용 원가 단위·공유 배포는 H08 전 실제 소유자와 결정한다. Core 규격이나 외부 engine의 필수 운영 모델이 아니다.

`runtime/python/ocp_runtime/trial.py`는 server-side gateway다. operator가 신뢰된 principal을 등록하며 외부 key는 256-bit 무작위 값으로 발급하고 SHA-256만 저장한다. 공개 회원가입/발급 endpoint는 없다. 내부 서비스 token을 key로 받지 않는다. tenant 헤더는 신원으로 사용하지 않으며 Body에 추가한 tenant는 Core 계약이 거절한다.

정책은 provider의 실제 descriptor digest에 결속한다. 원 descriptor는 바꾸지 않는다. 환경 projection에는 source catalog hash와 별도의 versioned policy를 표시하고 원 digest를 projection의 digest라고 부르지 않는다. capability/configuration이 변하면 거절한다. 실제 Omelet 원 catalog와의 대응표는 아직 없다.

기본값은 계획의 제안인 차량 2~3대, 방문 20개, solver budget 5초, 조직별 동시 1건·하루 30회·14일이다. 단일 차량은 reference에서 검증했지만 Omelet 경로 검증 전 trial에서는 거절한다. 총 420회와 일/기간/전체 예약 compute ms 상한도 집행한다. 수치는 미승인 상품 정책이며 운영 원가·신원·부하 검증 뒤 확정해야 한다.

SQLite BEGIN IMMEDIATE로 인증·entitlement·원자적 quota 예약·idempotency를 처리한다. key 회전/재발급·UTC 날짜 변경·프로세스 재시작으로 조직의 기간 예산이 초기화되지 않는다. 같은 조직+idempotency key+동일 요청은 한 번만 실행한다. 내용이 다르면 conflict다. 다른 조직의 결과를 조회할 수 없다. 만료·회수된 key는 replay도 거절한다. 평가도 인증·entitlement를 확인한다. async job/취소 기능은 미지원이며 가짜 성공을 반환하지 않는다.

응답 불명·crash 후 running/uncertain 예약은 자동으로 해제하거나 재실행하지 않는다. 실제 upstream 상태를 확인한 operator의 별도 복구 절차가 필요하다. 요청한 전체 compute budget을 보수적으로 예약하며 실패해도 환불하지 않는다. 관측 wall latency는 따로 기록한다. 예약 ms는 청구 금액이나 실제 solver CPU 측정이 아니다. 실제 비용 환산과 upstream hard limit 검증은 H08의 조건이다. 이 gateway만으로 임의의 엔진 프로세스를 강제 종료하지 않는다.

DB는 owner-only 0600이며 입력 원문 대신 digest, principal, quota, 상태, 결과를 보관한다. 결과는 1일 후 replay를 거절하고 operator의 `purge_results()`로 제거한다. 사용량/digest는 유지한다. 이 기간은 로컬 합성 검사용 제안이며 실제 고객 데이터의 보존·삭제 조건 승인이 아니다. 여러 서버·분산 DB·실제 신원 공급자·운영 TLS의 검증을 주장하지 않는다.

H07은 실제 reference solve/HTTP, 합성 key, 주입 clock·engine crash·동시 호출로 경계를 검사한다. 실제 외부 key→Omelet solve→평가→회수/만료/quota는 H08에서 별도로 확인한다.
