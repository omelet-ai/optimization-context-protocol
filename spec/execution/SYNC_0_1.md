# 동기 실행 profile 0.1 후보

식별자는 `execution.sync@0.1.0`이다. 로컬 함수 또는 선언한 transport에서 하나의 명시 request를 받아 하나의 result/failure를 반환한다. Core 참조는 [Core 0.1](../core/CORE_0_1.md)이다.

provider는 입력·configuration·버전을 검증한 뒤 계산한다. `budget.time_limit_ms`는 solver에 적용할 요청 상한이며 준비·직렬화·전체 호출 deadline과 구분한다. 구현은 적용하는 시간 측정 범위와 실제 budget을 문서화한다. caller deadline이 먼저 끝나면 engine의 종료나 원격 취소 완료를 추정하지 않는다.

job ID·submit/poll/cancel·멱등 key·tenant·DB는 이 profile의 기능이 아니다. sync-only provider에 async 요청이 오면 거절한다. sync 호출을 job 완료처럼 꾸미지 않는다. async profile은 실제 job 수명·소유권·취소·복구·멱등성 검사를 구현할 때 별도 버전으로 추가한다.

local 실행은 `binding.in_process@0.1.0`, `environment.local@0.1.0`의 후보 조합을 사용한다. 신뢰된 단일 사용자 프로세스의 호출 경계이며 인증·원격 tenant 격리·멀티프로세스 복구를 인증하지 않는다. 원격 HTTP와 MCP는 같은 메시지 의미를 보존하는 별도 binding이다.
