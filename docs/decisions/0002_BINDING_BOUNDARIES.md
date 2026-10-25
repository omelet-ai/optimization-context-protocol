# Binding 검증에서 확정한 구현 경계

Core 0.1.0 후보의 의미를 유지하면서 HTTP·TypeScript·MCP binding을 추가했다. 외부 배포 전 개발 후보이므로 최초 0.1.0 정본에 포함하며 이미 게시한 버전을 덮어쓴 것이 아니다. H01~H06 consumer를 다시 검사한다.

- TypeScript와 같은 JSON 교환 범위를 유지하려고 Python의 정수값 float도 안전 정수 범위를 검사한다. `1e16` 우회 입력을 회귀 검사에 추가했다.
- SDK는 중복 metric/constraint/objective ID를 거절한다. 독립 conformance는 routing profile 밖의 추가 optimized/enforced claim을 거절한다.
- MCP SDK의 일반 dict 반환 대신 명시적인 CallToolResult를 사용해 구조화 Core envelope와 실패 flag를 전달한다. 실제 stdio Client로 검증한다.
- OCP async profile은 미선언 상태다. SDK의 async 함수나 MCP transport의 실행 방식을 job 지원으로 해석하지 않는다.
- loopback 개발 HTTP 서버는 외부 서비스 배포용이 아니다. 실제 trial 환경·TLS·신원·비용 검증은 별도 승인과 H08 증거가 필요하다.
