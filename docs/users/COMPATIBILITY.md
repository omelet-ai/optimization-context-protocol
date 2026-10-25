# Candidate compatibility

| Component | Version / checked environment | Scope |
| --- | --- | --- |
| Core / sync / routing.basic | 0.1.0 candidate | strict JSON; exact versions; explicit integer meter/kg |
| Python SDK / adapter | 0.1.0, CPython 3.12.15, macOS arm64 | wheel install, own input, real OR-Tools 9.15.6755 |
| TypeScript client | 0.1.0, Node 24.22.0 / TS 7.0.2 | npm tarball, build, HTTP App B |
| HTTP binding | 0.1.0 | loopback only; no async job API |
| MCP stdio | mcp 2.3.0 / protocol 2026-07-28 | official SDK subprocess host; other hosts untested |
| conformance | ocp.transcript 0.1.0 | independent transcript semantics; own packaged schemas |
| assignment.fixture | 0.1.0 | schema/requirements/feasible witness only; no solver |
| local trial policy | 0.1.0 local candidate | SQLite + operator-provisioned synthetic principal/key; no public signup |
| routing.coordinates | 0.1.0 candidate | Haversine R=6371000 m, ceil; independent reference and checker |
| actual local Omelet adapter | catalog 1.4.0 / compiler 1.2.0 / API 1.0, exact document pin | H16 real loopback engine through trial keys; external operations unverified |
| Python/TypeScript × reference/Omelet | H17 local candidate | four installed-app combinations on routing.coordinates; no external human acceptance |

공개 전 candidate 0.1.0은 아직 동결되지 않았다. 사용할 때 artifact SHA-256과 schema hash를 고정한다. 공개 후 계약·의미가 바뀌면 version 갱신, migration 문서, provider/consumer/conformance 재검증이 필요하며 기존 버전을 덮어쓰지 않는다.

알 수 없는 Core/profile/capability 버전과 필수 extension은 거절한다. optional extension은 advisory이며 목적·제약 의미를 바꾸지 않는다. 다른 엔진으로 교환할 때는 profile 교집합·단위·행렬·반올림·cost coefficient를 대조한다. 같은 해와 동일 실행 시간을 보장하지 않는다. 공개 후의 지원 기간·폐기 일정은 실제 maintainer 결정이 필요하다.
