# runtime

`python/ocp_runtime`에 선택 HTTP·MCP stdio와 로컬 trial 정책 후보를 구현했다. SDK wheel에 포함하며 Core가 서버나 endpoint를 필수로 요구하지 않는다.

H06은 독립 설치한 실제 OR-Tools에 Python/TypeScript HTTP client와 공식 MCP SDK host를 연결한다. H07은 합성 신원·키를 사용해 SQLite 기반 quota·멱등성·만료·회수·격리를 검증한다. 최신 판정은 하네스에서 확인한다.

HTTP는 loopback 전용이다. 실제 Omelet trial, 외부 신원 발급, 금액 기준 원가 집행, 공개 운영·배포는 H08 이후의 별도 검증 대상이다. [binding](../spec/bindings/HTTP_MCP_0_1.md)과 [로컬 정책](../spec/environments/TRIAL_LOCAL_0_1.md)을 따른다.
