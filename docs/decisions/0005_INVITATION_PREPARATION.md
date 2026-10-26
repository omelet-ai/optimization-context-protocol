# 0005 — 초대 시험 운영과 MCP 연결 준비

상태: 비공개 구현 후보. 2026-10-26 사용자 위임에 따라 운영 책임을 요청 사용자에게 배정하고 빠른 소규모 시험을 준비한다. 라이선스/특허 검토 결과와 외부 배포 승인을 만들어 기록하지 않는다.

기존 H07/H16 정책을 유지하면서 `InvitationPolicy`를 추가한다. principal 5개·전체 50회·각 하루 5회/총 10회·14일·24시간 결과 캐시로 제한한다. 별도 DB의 정책 hash를 고정하므로 기존 캠페인 quota를 초기화하지 않는다. Core/좌표 profile/version은 바꾸지 않는다. 새로운 공개 회원가입, async 계약, 브라우저 앱은 추가하지 않는다.

운영자는 CLI로 발급·회수·중단·상태·백업·복구를 수행한다. 복구에는 원자적으로 보존한 upstream job ID, 동일 trusted tenant와 실제 종료 확인이 필요하다. 응답이 유실된 제출은 자동 재시도하지 않는다. 결과를 복구했다고 주장하지 않고 concurrency만 해제하며 예산은 유지한다.

초대자는 별도 key/endpoint/descriptor pin 파일과 설치 wheel을 받는다. MCP stdio bridge는 같은 HTTP adapter를 사용하며 공개 선택 binding은 유지한다. 공식 MCP SDK host와 실제 로컬 Foundry로 검사하고 Claude Code 실제 host 및 사외 HTTPS 시험은 별도로 기록한다.

H19는 H07/H11/H18을 선행으로 하는 독립적인 로컬 준비 관문이다. 설치된 operator server, MCP-only client, 실제 엔진, 독립 checker, quota/복구/파일 보호/연결 제한을 확인한다. D00/D01·H08/H09·H12의 승인·외부 과제를 대체하지 않는다.

운영 절차는 [초대 시험 운영](../development/INVITATION_OPERATIONS.md), 초대자 안내는 [시작하기](../users/INVITED_TRIAL.md)에 둔다.
