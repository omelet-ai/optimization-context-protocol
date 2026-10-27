# Candidate compatibility

| Component | Version / checked environment | Scope |
| --- | --- | --- |
| Core / sync / routing.basic | 0.1.0 candidate | strict JSON; exact versions; explicit integer meter/kg |
| Python SDK / adapter | 0.1.0, CPython 3.12.15, macOS arm64 | wheel install, own input, real OR-Tools 9.15.6755 |
| TypeScript client | 0.1.0, Node 24.22.0 / TS 7.0.2 | npm tarball, build, HTTP App B |
| HTTP binding | 0.1.0 | loopback only; no async job API |
| MCP stdio | mcp 2.3.0 / protocol 2026-07-28 | official SDK subprocess host; scoped Codex model pilot separately recorded, not general host certification |
| conformance | ocp.transcript 0.1.0 | independent transcript semantics; own packaged schemas |
| assignment.fixture | 0.1.0 | schema/requirements/feasible witness only; no solver |
| local trial policy | 0.1.0 local candidate | SQLite + operator-provisioned synthetic principal/key; no public signup |
| routing.coordinates | 0.1.0 candidate | Haversine R=6371000 m, ceil; independent reference and checker |
| actual local Omelet adapter | explicit catalog 1.3.0 or 1.4.0 (default) / compiler 1.2.0 / API 1.0, exact document pin | H16 real loopback engine through trial keys; no automatic version fallback; external operations unverified |
| Python/TypeScript × reference/Omelet | H17 local candidate | four installed-app combinations on routing.coordinates; no external human acceptance |
| installed Foundry client + TMS resolver | H18 local candidate / Node 22.23.3 | recorded main-based catalog 1.3.0, independent evaluation, original 1.4.0 smoke; see [scope](../decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md) |

공개 전 candidate 0.1.0은 아직 동결되지 않았다. 사용할 때 artifact SHA-256과 schema hash를 고정한다. 공개 후 계약·의미가 바뀌면 version 갱신, migration 문서, provider/consumer/conformance 재검증이 필요하며 기존 버전을 덮어쓰지 않는다.

알 수 없는 Core/profile/capability 버전과 필수 extension은 거절한다. optional extension은 advisory이며 목적·제약 의미를 바꾸지 않는다. 다른 엔진으로 교환할 때는 profile 교집합·단위·행렬·반올림·cost coefficient를 대조한다. 같은 해와 동일 실행 시간을 보장하지 않는다. 공개 후의 지원 기간·폐기 일정은 실제 maintainer 결정이 필요하다.

2026-10-26 onboarding candidate: Core/profile wire 버전은 유지하고 TypeScript evaluate 및 MCP request-guide resource를 추가했다. App B는 --request-id가 필수다. [변경·migration](../decisions/0006_DEVELOPER_ONBOARDING.md)과 새 artifact hash를 함께 사용한다.

2026-10-27 context candidate: 선택적 `ocp_context()`를 여섯 번째 MCP 도구로 추가했다. 성공한 context는 Core envelope가 아닌 guide 객체이며 기존 다섯 연산은 유지한다. [모델 컨텍스트 변경](../decisions/0007_MODEL_VISIBLE_CONTEXT.md)의 동적 발견·실패 처리와 artifact hash를 적용한다. 실제 LLM/호스트 수락은 별도 H24다.

2026-10-27 proof-checker candidate: 독립 checker는 `routing.basic`의 두 분석적 infeasible 증명에서 입력으로 재계산한 수치와 `proof.evidence`의 수치를 대조한다. 참인 불가능 판정에 잘못된 설명 숫자가 붙어 있어도 거절한다. 기존 provider의 올바른 출력과 Core envelope 형식은 유지한다. 누락·변조된 수치를 허용하던 checker 동작은 호환 대상으로 보존하지 않는다. [profile 규칙](../../spec/profiles/ROUTING_BASIC_0_1.md)에 맞춰 제3자 provider를 수정하고 새 checker artifact hash를 고정한다. 아직 공개·동결되지 않은 0.1.0 후보의 보완이며, H05 결함 주입과 설치된 provider/consumer/conformance 회귀 검증을 다시 수행해야 한다.
