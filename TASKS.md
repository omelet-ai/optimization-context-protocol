# 작업 원장

상태: H01~H07·H11·H15~H18에 더해 초대 운영·설치 MCP 준비 H19를 구현·검사에 연결했다. 실제 외부 trial·사용자·공개 관문은 미완료다. 2026-10-26 요청 사용자가 운영·기술·지원 및 권리 검토 조정 책임을 맡았다. 권리 검토 결과를 담당 배정으로 대신하지 않는다. 기술 단계의 현재 판정은 [검증 환경](docs/development/LOCAL_RUNTIME.md)의 Python으로 `tools/harness.py status`를 실행해 계산하며 아래 작업의 전체 완료와 구분한다.

| ID | 작업 | 상태 | 첫 완료 증거 |
| --- | --- | --- | --- |
| BOOT-00 | 독립 폴더·계획·원본 출처·합성 사례 준비 | 파일 준비 | verify_workspace 결과 |
| HARNESS-00 | 단계 의존성·실행기·증거 만료·진급 차단 | 구현·검사 연결, 최신 상태는 H00 | 하네스 회귀 검사와 H00 실행 보고서 |
| OSS-00 | 외부 과제·P0 권리·담당·예산 | 과제·계측 준비, 사용자 담당 배정, 권리 결과·배포/비용 결정 대기 | 공개/보류 결정과 실제 담당 |
| OSS-01 | Core/profile/binding RFC | 비공개 기술 후보 구현, 최신 H01 판정 | Core schema·sync 후보·Omelet mapping, 35개 계약 검사 |
| OSS-02 | 의미·오류·평가 fixture | routing 후보·독립 평가 구현, 최신 H02 판정 | 34개 정상·거부·반례 검사, bounded oracle |
| OSS-03 | library/SDK/REST adapter port·client | Python port/client·OR-Tools adapter 후보 구현, H03 판정 | 28개 실제 호출·거절·결함 주입 검사. HTTP/TypeScript 후보는 H06 |
| OSS-04 | OR-Tools reference·App A | 독립 설치·App A 후보 구현, H04 판정 | 14개 검사: 오프라인 설치·실제 solve·자기 입력·독립 평가·실패 진단·초기 준비 |
| OSS-05 | HTTP/async/MCP·환경 binding | sync HTTP·MCP·TypeScript 후보 구현, H06 판정 | 21개 loopback·stdio·App B·응답 제한 검사. async 미지원 |
| OSS-06 | Omelet engine·App B 교차 연결 | H17 로컬 후보 구현·검사 연결, H09 외부 운영 대기 | 설치 Python/TypeScript × 실제 OR-Tools/로컬 Omelet 네 조합 |
| OSS-07 | Studio 최소 smoke | private draft PR 구현·검증, H10 외부 선행 대기 | [소비자 원장](docs/development/INTERNAL_CONSUMER_STATUS.md)의 브라우저→API→실제 엔진 |
| OSS-08 | Foundry 조회·resolve 시험 | 같은 draft PR에 구현·검증, H18에 main 기반 provider 호환 검사 연결 | 같은 package의 공개 entrypoint를 쓰는 TMS resolver |
| OSS-09 | 다른 도메인·공통 conformance | transcript runner·assignment fixture 구현, H05 판정 | 23개 결함 검출·CLI·도메인 분리 검사. assignment 실제 solve 미구현 |
| OSS-10 | 배포 artifact·호환성 | 비공개 선정 소스·wheel·tarball 구현, H11 판정 | 14개 clean install/build·BYO·소스 일치·문서 검사 |
| OSS-11 | 외부 DX·기여 운영 | 세 입구·BYO·호환·기여·실제 과제·계측 도구 준비. H12 대기 | H11에 계측 회귀 20개 추가. [외부 과제지](docs/users/EXTERNAL_DX_STUDY.md)의 실제 수행은 미완료 |
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
| H18 | 기록된 main provider와 설치 Foundry client·기존 TMS resolver. H17·D02 선행 |
| H19 | 초대 운영 CLI·복구·전체 호출 상한·설치 MCP client→실제 로컬 엔진. H07·H11·H18 선행 |
| H10 | OSS-07 Studio, OSS-08 Foundry 최소 소비 |
| H11 → H12 | OSS-10 artifact, OSS-11 문서·BYO·실제 외부 과제 |
| H13 → H14 | OSS-12 출시 후보 → 승인 게시·사후 확인 |
| D00~D03 | 권리·운영 책임 / 외부 환경 / 내부 저장소 범위 / 게시 승인 |
| F01·F02·F03 | 공개 후 30일·90일 / OSS-13 별도 내부 후속 |

다음 기술 개발은 하네스 `next`의 현재 결과를 따른다. 2026-10-25의 사용자 위임으로 실제 로컬 API 준비에 이어 좌표 profile·trial adapter·키/한도 집행·두 앱과 두 엔진의 교차 후보를 구현했다. 원격 유료 서비스를 사용하지 않으며 로컬 설정·인증정보·보고서는 추적에서 제외한다. 기존 basic 행렬을 좌표로 변환하지 않는다. H08/H09의 전체 외부 운영 조건과 H10·H12~H14의 선행 관문은 유지한다. P0 미완료 중의 로컬 기술 후보 개발은 OSS-00·공개 권리·운영 준비의 완료가 아니다. 에이전트가 검사·수정·증거 갱신을 수행한다.

좌표 adapter·실제 upstream pin·trial 신원/한도 연결과 설치 소비자 네 조합을 구현했다. 현재 증거는 H15~H18의 최신 판정을 사용한다. 이 로컬 후보 분리의 이유와 기존 외부 관문 보존은 [결정 기록](docs/decisions/0003_COORDINATES_AND_LOCAL_TRIAL.md)에 있다. 사내 최소 consumer는 draft PR까지 구현했으며 D02에 실제 승인 원문 대조를 연결했다. 실제 외부 신원 발급·권리/운영 결정·main 제품 반영·사용자 시험은 남아 있다.

2026-10-25 후속 작업에서 현재 Python 환경과 소스 폴더의 bytecode를 구분하고, 소스 식별이 바뀐 로컬 엔진을 재기동했다. 과거 PASS를 그대로 재사용하지 않고 현재 선행부터 검사한다. `decision` 모드는 이미 받은 사용자 지시의 출처·scope를 검사하며 D00/D01/D03의 미정 결정을 대신 채우지 않는다. 외부 DX 도구의 합성 회귀 검사는 실제 외부 개발자 수 0명으로 보고한다.

기록된 main의 native source를 변경하지 않고 catalog 1.3.0을 명시적으로 선택하는 경로와 H18을 추가했다. 기존 1.4.0 기본값·전체 문서 pin·공통 계약은 유지한다. 이 좁은 연동의 provider migration 요구는 [호환성 결정](docs/decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md)으로 해소하며 외부 시험·H10·merge 조건은 유지한다.

초대 시험은 [운영 절차](docs/development/INVITATION_OPERATIONS.md)와 [초대자 안내](docs/users/INVITED_TRIAL.md)를 사용한다. 5명·전체 50회·각 하루 5회/총 10회·14일, 기존 로컬 엔진과 단기 HTTPS 경로를 준비한다. H19는 [결정 기록](docs/decisions/0005_INVITATION_PREPARATION.md)의 설치·로컬 검사이며 외부 호스팅·실제 Claude Code·외부 참여자 증거는 별도다.

H20은 외부 엔지니어 자동 리허설에서 발견한 U01~U09의 회귀 단계다. strict JSON, 명시 request ID, BYO 실패 종료, 새 환경의 build·설치·진단, MCP request-guide, TypeScript 평가와 transcript 예제를 새 꾸러미로 검사한다. [변경 기록](docs/decisions/0006_DEVELOPER_ONBOARDING.md)을 따르며 현재 판정은 하네스에서 확인한다. 실제 외부 사람의 H12 및 게시 승인은 별도다.
