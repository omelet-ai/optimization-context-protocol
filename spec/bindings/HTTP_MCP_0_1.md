# Optional HTTP and MCP bindings 0.1.0

상태: 비공개 기술 후보. Core는 아래 endpoint·MCP·서버·TypeScript를 공통 필수로 요구하지 않는다. 두 binding 모두 `execution.sync@0.1.0`만 제공한다. job 생성·조회·취소·복구를 선언하지 않으며 async 요청은 거절한다.

| HTTP | 입력 | 출력 |
| --- | --- | --- |
| GET /v1/capability | 없음 | capability |
| POST /v1/requirements | `{configuration}` | requirements/failure |
| POST /v1/validate | Core request | validation |
| POST /v1/execute | Core request | result/failure |
| POST /v1/evaluate | `{request, solution}` | evaluation/failure |

본문은 UTF-8 strict JSON이다. 중복 key·nonfinite·안전 범위를 넘는 정수·지원하지 않는 의미를 거절한다. 전송 성공은 계산 성공과 다르므로 항상 kind/status를 확인한다. 도메인 실패는 HTTP 200의 failure, framing·크기·origin·경로 오류는 4xx와 failure다. 요청 최대 128 KiB, 기본 참조 서버는 loopback 127.0.0.1에서만 듣는다. Host 일치와 Origin 부재를 확인한다. 외부 trial의 TLS·신원·quota는 H07/H08의 별도 환경 정책이다.

Python HTTPAdapter와 TypeScript Client는 자동 redirect/retry를 하지 않는다. 응답은 최대 1 MiB이며 TypeScript는 Content-Length가 없거나 잘못된 경우에도 읽은 byte 수를 제한하고 초과 시 stream을 취소한다. 응답 손실은 실행 여부 불명이며 같은 solve를 자동 재전송하지 않는다. request identity, profile/version, effective configuration 보존을 검사한다. TypeScript의 canonical Core schema는 build 시 복사하며 정본 일치를 확인한다. Node 24.22.0 / TypeScript 7.0.2 / Ajv 8.20.0 / jsonc-parser 3.3.1 조합을 검사한다.

MCP는 시작 안내 `ocp_context`와 기존 연산 `ocp_describe`, `ocp_requirements`, `ocp_validate`, `ocp_execute`, `ocp_evaluate`를 제공한다. stdio 프로세스로 실행한다. 다섯 연산의 `structured_content`는 Core envelope이며, `ocp_context`의 성공은 guide 객체다. text는 같은 JSON이며 Core failure에는 `is_error=true`다. MCP의 async 호출 API는 OCP async job을 의미하지 않는다. 취소 도구를 제공하지 않는다.

검증 host는 별도 프로세스를 실행하는 공식 Python MCP Client 2.3.0, protocol 2026-07-28이다. Claude Desktop·다른 host·다른 protocol 조합은 미검증이다. 실제 OR-Tools를 호출한 HTTP/TypeScript/MCP 결과를 독립 평가한다. 예외·인증정보·요청 본문은 서버 로그에 출력하지 않는다.

참고: [MCP SDK](https://py.sdk.modelcontextprotocol.io/), [공식 Client](https://py.sdk.modelcontextprotocol.io/client/), [Ajv schema language](https://ajv.js.org/guide/schema-language.html), [JSON parser](https://github.com/microsoft/node-jsonc-parser). 패키지 이름·버전은 비공개 후보이며 registry 게시 승인과 별도다.

후보 추가 기능: MCP의 `ocp_context()`와 선택적 `ocp://request-guide/0.1.0` JSON resource는 동일한 capability·requirements·Core request schema·알려진 input profile schema·provider defaults가 반영된 request template·결과 해석 규칙을 제공한다. 조회는 solve하지 않는다. 알 수 없는 profile의 input schema는 null이며 추측하지 않는다. resource도 failure이면 template을 사용하지 않는다. 기존 다섯 연산과 Core wire schema는 유지한다. 여섯 도구의 동적 발견 및 guide 소비자 이행은 [모델 컨텍스트 변경](../../docs/decisions/0007_MODEL_VISIBLE_CONTEXT.md)을 따른다. TypeScript Client.evaluate(request, solution)는 기존 /v1/evaluate를 호출하고 request ID·capability·profile을 대조한다. CLI migration은 [개발자 연결 변경](../../docs/decisions/0006_DEVELOPER_ONBOARDING.md)을 따른다.
