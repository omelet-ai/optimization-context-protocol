# 작업 원장

상태: H01~H07·H11 및 좌표/실제 로컬 연동 H15~H17의 비공개 구현·검사 연결. 실제 Omelet trial·외부 사용자·공개 관문은 미완료다. 담당 실명은 미정이며 이전 계획의 목표를 완료 실적으로 바꾸지 않는다. 기술 단계의 현재 판정은 [검증 환경](docs/development/LOCAL_RUNTIME.md)의 Python으로 `tools/harness.py status`를 실행해 계산하며 아래 작업의 전체 완료와 구분한다.

| ID | 작업 | 상태 | 첫 완료 증거 |
| --- | --- | --- | --- |
| BOOT-00 | 독립 폴더·계획·원본 출처·합성 사례 준비 | 파일 준비 | verify_workspace 결과 |
| HARNESS-00 | 단계 의존성·실행기·증거 만료·진급 차단 | 구현·검사 연결, 최신 상태는 H00 | 하네스 회귀 검사와 H00 실행 보고서 |
| OSS-00 | 외부 과제·P0 권리·실명·예산 | 미착수 | 공개/보류 결정과 실제 담당 |
| OSS-01 | Core/profile/binding RFC | 비공개 기술 후보 구현, 최신 H01 판정 | Core schema·sync 후보·Omelet mapping, 35개 계약 검사 |
| OSS-02 | 의미·오류·평가 fixture | routing 후보·독립 평가 구현, 최신 H02 판정 | 34개 정상·거부·반례 검사, bounded oracle |
| OSS-03 | library/SDK/REST adapter port·client | Python port/client·OR-Tools adapter 후보 구현, H03 판정 | 28개 실제 호출·거절·결함 주입 검사. HTTP/TypeScript 후보는 H06 |
| OSS-04 | OR-Tools reference·App A | 독립 설치·App A 후보 구현, H04 판정 | 12개 검사: 오프라인 설치·실제 solve·자기 입력·독립 평가 |
| OSS-05 | HTTP/async/MCP·환경 binding | sync HTTP·MCP·TypeScript 후보 구현, H06 판정 | 21개 loopback·stdio·App B·응답 제한 검사. async 미지원 |
| OSS-06 | Omelet engine·App B 교차 연결 | H17 로컬 후보 구현·검사 연결, H09 외부 운영 대기 | 설치 Python/TypeScript × 실제 OR-Tools/로컬 Omelet 네 조합 |
| OSS-07 | Studio 최소 smoke | 후속 연동 대기 | 한 profile 소비 |
| OSS-08 | Foundry 조회·resolve 시험 | 후속 연동 대기 | 작은 consumer 검사 |
| OSS-09 | 다른 도메인·공통 conformance | transcript runner·assignment fixture 구현, H05 판정 | 23개 결함 검출·CLI·도메인 분리 검사. assignment 실제 solve 미구현 |
| OSS-10 | 배포 artifact·호환성 | 비공개 선정 소스·wheel·tarball 구현, H11 판정 | 14개 clean install/build·BYO·소스 일치·문서 검사 |
| OSS-11 | 외부 DX·기여 운영 | 세 입구·BYO·호환·기여 안내 준비. 실제 사용자 H12 대기 | H11 기술 검사와 15분·60분 실제 시험을 구분 |
| OSS-12 | 공개 RC·trial 공동 출시 | P0 관문 대기 | 승인·게시·재설치 |
| OSS-13 | Application Spec·AppKit 후속 | 첫 윈도우 밖 | 별도 승인된 내부 이행 |
| OSS-14 | trial 신원·quota·키·만료·회수 | 로컬 정책 H07, 실제 로컬 key→Omelet 연결 H16 후보. H08 외부 운영 대기 | 28개 로컬 실제 reference/HTTP·동시성·재시도·격리 검사 |

선행 관계는 [하네스 정의](harness/plan.json)를 따른다. 상세 내부 출시 계획은 로컬 원본 보유 공간의 `docs/plans/OCP_OPEN_SOURCE_RELEASE_PLAN.md`에 보존하며 원격 추적에서 제외한다. 이 폴더에서는 공개 표준·참조 구현을 개발하고 실제 사내 제품 변경은 해당 저장소의 별도 범위로 관리한다.

## 단계와 작업 추적

진행 절차와 단계별 완료 기준은 [하네스 안내](harness/README.md)에 둔다. [기계 판독 정의](harness/plan.json)는 BOOT-00·HARNESS-00과 OSS-00~14 전체를 추적한다. H00의 통과는 제품 구현·공개 준비 완료를 의미하지 않는다.

| 기술 단계 | 연결 작업 |
| --- | --- |
| H00 | BOOT-00, HARNESS-00 |
| H01 → H02 → H03 → H04 | OSS-01 → OSS-02 → OSS-03 → OSS-04 |
| H05 | OSS-09 독립 conformance와 두 번째 도메인 |
| H06 | OSS-05 binding, OSS-03 TypeScript 소비자 |
| H07 → H08 | OSS-14 로컬 정책 → 실제 trial 집행 |
| H09 | OSS-06 두 앱 × 두 엔진의 외부 trial 전제 |
| H15 → H16 → H17 | 좌표 계약 → 실제 로컬 trial → 설치 앱 두 개 × 실제 엔진 두 개의 독립 후보 |
| H10 | OSS-07 Studio, OSS-08 Foundry 최소 소비 |
| H11 → H12 | OSS-10 artifact, OSS-11 문서·BYO·실제 외부 과제 |
| H13 → H14 | OSS-12 출시 후보 → 승인 게시·사후 확인 |
| D00~D03 | 권리·운영 책임 / 외부 환경 / 내부 저장소 범위 / 게시 승인 |
| F01·F02·F03 | 공개 후 30일·90일 / OSS-13 별도 내부 후속 |

다음 기술 개발은 하네스 `next`의 현재 결과를 따른다. 2026-10-25의 사용자 위임으로 실제 로컬 API 준비에 이어 좌표 profile·trial adapter·키/한도 집행·두 앱과 두 엔진의 교차 후보를 구현했다. 원격 유료 서비스를 사용하지 않으며 로컬 설정·인증정보·보고서는 추적에서 제외한다. 기존 basic 행렬을 좌표로 변환하지 않는다. H08/H09의 전체 외부 운영 조건과 H10·H12~H14의 선행 관문은 유지한다. P0 미완료 중의 로컬 기술 후보 개발은 OSS-00·공개 권리·운영 준비의 완료가 아니다. 에이전트가 검사·수정·증거 갱신을 수행한다.

좌표 adapter·실제 upstream pin·trial 신원/한도 연결과 설치 소비자 네 조합을 구현했다. 현재 증거는 H15~H17의 최신 판정을 사용한다. 이 로컬 후보 분리의 이유와 기존 외부 관문 보존은 [결정 기록](docs/decisions/0003_COORDINATES_AND_LOCAL_TRIAL.md)에 있다. 실제 외부 신원 발급·권리/운영 결정·사내 consumer 변경·사용자 시험은 남아 있으며 자동 검증으로 승인 사실을 만들지 않는다.
