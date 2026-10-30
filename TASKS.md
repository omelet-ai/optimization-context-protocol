# 작업 원장

## 2026-10-30: TMS adoption preparation — local review

The owner selected TMS/dispatch as the first commercial-adoption evaluation.
This candidate adds a reproducible routing exercise, an application-field and
unsupported-requirement mapping, explicit human-study evidence rules, and links
from README/site to Omelet's existing commercial contact page. It changes no
protocol, solver, runtime package or existing Foundry repository. The website
palette from main a612d2a is retained in this isolated review candidate.

Validation and the TMS pilot plan are local review evidence; automated sample
execution is not external-human acceptance or a customer pilot. Harness stages
are not advanced by standalone document/site/release checks. Publication,
participant contact, commercial-engine access and real customer data are not
performed by this preparation. The exact patch and local preview are reviewed
before any new scoped publication.

현재 공개 상태(2026-10-29): Core·native 소스와 Apache-2.0 고지는 공개되었고 기존 Pages 사이트가 운영 중이다. 아래 초기 표와 날짜별 기록은 개발 이력이다. 최신 준비 범위는 [프리릴리스 계획](docs/development/PREVIEW_RELEASE.md)과 H63을 따른다. H63은 선택 소스로 만든 동일 ZIP의 새 설치·실제 앱/MCP·검산을 검사하며 전체 로컬 선행을 갱신한 뒤 진급한다. 실제 외부 개발자와 내부 담당자 수락은 NOT_RUN이다. 2026-10-29 사용자는 검증된 소스 commit/push, 첫 GitHub 프리릴리스 자산 게시와 기존 Pages 갱신을 승인했다. 레지스트리·추가 모델 실행·외부 trial은 별도 범위다.

## 초기 개발 이력


상태: H01~H07·H11·H15~H18에 더해 초대 운영·설치 MCP 준비 H19를 구현·검사에 연결했다. 실제 외부 trial·사용자·공개 관문은 미완료다. 2026-10-26 요청 사용자가 운영·기술·지원 및 권리 검토 조정 책임을 맡았다. 권리 검토 결과를 담당 배정으로 대신하지 않는다. 기술 단계의 현재 판정은 [검증 환경](docs/development/LOCAL_RUNTIME.md)의 Python으로 `tools/harness.py status`를 실행해 계산하며 아래 작업의 전체 완료와 구분한다.

| ID | 작업 | 상태 | 첫 완료 증거 |
| --- | --- | --- | --- |
| BOOT-00 | 독립 폴더·계획·원본 출처·합성 사례 준비 | 파일 준비 | verify_workspace 결과 |
| HARNESS-00 | 단계 의존성·실행기·증거 만료·진급 차단 | 구현·검사 연결, 최신 상태는 H00 | 하네스 회귀 검사와 H00 실행 보고서 |
| OSS-00 | 외부 과제·P0 권리·담당·예산 | 과제·계측 준비, 사용자 담당 배정, 권리 결과·배포/비용 결정 대기 | 공개/보류 결정과 실제 담당 |
| OSS-01 | Core/profile/binding RFC | 비공개 기술 후보 구현, 최신 H01 판정 | Core schema·sync 후보·Omelet mapping, 35개 계약 검사 |
| OSS-02 | 의미·오류·평가 fixture | routing 후보·독립 평가 구현, 최신 H02 판정 | 34개 정상·거부·반례 검사, bounded oracle |
| OSS-03 | library/SDK/REST adapter port·client | Python port/client·OR-Tools adapter 후보 구현, H03 판정 | 28개 실제 호출·거절·결함 주입 검사. HTTP/TypeScript 후보는 H06 |
| OSS-04 | OR-Tools reference·App A | 독립 설치·App A 후보 구현, H04 판정 | 16개 검사: 오프라인 설치·실제 solve·자기 입력·독립 평가·단계별 실패 진단·cold 준비 |
| OSS-05 | HTTP/async/MCP·환경 binding | sync HTTP·MCP·TypeScript 후보 구현, H06 판정 | 21개 loopback·stdio·App B·응답 제한 검사. async 미지원 |
| OSS-06 | Omelet engine·App B 교차 연결 | H17 로컬 후보 구현·검사 연결, H09 외부 운영 대기 | 설치 Python/TypeScript × 실제 OR-Tools/로컬 Omelet 네 조합 |
| OSS-07 | Studio 최소 smoke | private draft PR 구현·검증, H10 외부 선행 대기 | [소비자 원장](docs/development/INTERNAL_CONSUMER_STATUS.md)의 브라우저→API→실제 엔진 |
| OSS-08 | Foundry 조회·resolve 시험 | 같은 draft PR에 구현·검증, H18에 main 기반 provider 호환 검사 연결 | 같은 package의 공개 entrypoint를 쓰는 TMS resolver |
| OSS-09 | 다른 도메인·공통 conformance | transcript runner·assignment fixture 구현, H05 판정 | 25개 결함 검출·CLI·도메인 분리 검사. 분석 증명의 수치도 입력과 대조. assignment fixture 유지; 실제 worker/inventory는 H26~H30 별도 검증 |
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

H21은 [공개 사이트의 로컬 후보](site/README.md)를 추적한다. 영문 중심 10개 페이지·한국어 소개·세 시작 경로·실제 계산 예제·명령 복사와 설치 꾸러미를 구현했다. 명시 파일/링크/해시와 새 설치·Python/TypeScript/BYO 실행은 H21에서 검사하고, 브라우저 화면·입력 관찰은 정확한 site manifest에 별도 기록한다. 잠금 등으로 수행하지 못한 UI 검사를 PASS로 대신하지 않는다. 공개 주소·권리·라이선스·게시와 실제 외부 사람 수락은 미완료다.

H21 준비 시간 초과는 새 설치의 네이티브 엔진 로딩과 예제 실행을 분리해 처리한다. 시작 60초·준비 후 실행 30초·solve 1,000ms의 독립 상한과 고정 단계별 실패 진단을 적용하며, 첫 실행을 미리 로딩하거나 자동 재시도로 대체하지 않는다. 시작/실행 초과와 자식 프로세스 정리도 회귀 검사한다. 배포 보류를 유지한다.

다운로드 꾸러미를 저장소 밖에서 사용하는 엔지니어 리허설의 후속으로, 첫 README에 영문 세 시작 경로와 no-key 설치·앱·엔진 연결을 제공한다. 로컬 trace 파일 충돌을 초대 오류로 잘못 안내하던 문제는 별도 진단과 실행 전 경로 검사로 수정한다. H20은 기존 파일·끊어진 symlink·없는 부모 폴더를 거절하고 원본과 호출 횟수를 보존하는 회귀를 포함한다. 에이전트 리허설과 실제 외부 개발자 수락은 계속 구분한다.

H22는 외부 평가 후 첫 성공 경로를 추적한다. 새 꾸러미의 `start.py`가 검증·설치·실제 두 엔진 실행·독립 검사를 연결한다. 같은 앱·입력, 변경 입력 재계산, 잘못된 단위·용량·누락·비용과 실제 deadline, checker-only 환경, 기존 환경 보존을 검사한다. [GitHub 공개 준비](docs/development/GITHUB_LAUNCH.md)에 영문 README·기여/보안/이슈/PR 자료와 후속 Linux·비라우팅·사람 시험을 정리한다. 실제 외부 수락·라이선스 적용·게시를 완료로 간주하지 않는다.

H23은 [LLM 컨텍스트 검증](docs/development/LLM_CONTEXT_VALIDATION.md)의 로컬 단계를 추적한다. `ocp_context` 도구로 리소스를 읽지 않는 호스트에도 capability·입력 schema·template·결과 의미를 제공한다. 새 설치, 실제 MCP 통신, 정상 계산·검산, 누락·단위·미지원 제약·profile 차이·deadline·용량 증명·지시문 형태 ID를 검사한다. 실제 모델용 8개 과제와 별도 rubric을 생성하는 것은 모델 실행과 구분한다. H24의 승인된 첫 모델 시험은 수행되었으며, 호스트 설정 실패도 분모에 남긴다. 상세 도구 기록·답변 판정·사용량은 비공개 실행 증거에 보관하고 H24 전체 수락이나 범용 LLM 호환성으로 확대하지 않는다. H23 PASS와 제한된 모델 시험은 H12 외부 개발자 수락을 대신하지 않는다.

첫 성공 개선의 전체 회귀에서 H04 첫 프로세스의 15초 초과가 다시 관찰되었다. 실제 backend 생성 뒤 준비 신호를 계측해 cold 준비 60초·준비 후 실행 15초를 분리한다. 같은 cold 프로세스에서 실제 App A를 실행하고 준비 이전/이후 초과 및 실패 종료를 검사하며, 재시도나 사전 실행은 추가하지 않는다. solver 1,000ms 및 1ms 의미는 유지한다.

H25는 no-key LLM 연결의 설치 공백을 해결한다. `start.py --mcp`는 reference·MCP·독립 checker를 함께 설치하고 실제 stdio 컨텍스트를 진단한다. `local_agent doctor/smoke/config`는 계산 없는 진단·한 번의 실제 계산/독립 검산·설정 출력을 구분한다. 새 ZIP·HOME·venv의 Python/Node 앱과 잘못된 입력 차단을 검사하고 영문 시작 안내·과제·피드백 양식·소스 해시를 평가 꾸러미에 포함한다. [재현 절차](docs/development/NO_KEY_EVALUATION.md)를 따르며 Linux/다른 기기의 결과는 정확한 ZIP hash를 가진 별도 실행 보고서로 확인한다. H25는 H23에 의존하고 외부 H24를 우회하거나 완료하지 않는다. 추가 모델 호출·공유·배포 없이 로컬 준비만 수행한다.

## 2026-10-27: 세 도메인 실제 실행 확대

사용자가 워커 스케줄링과 재고 발주 profile·실제 solver·독립 checker 및 공통 앱/MCP 구현을 승인했다. 기존 두 번째 도메인 fixture 범위를 확장하되 assignment.fixture와 Core 의미는 유지한다. H26 계약 → H27 워커 → H28 재고 → H29 공통 앱/MCP → H30 새 설치·평가 준비 순서이며 각 현재 선행 PASS 후 진급한다. 작은 합성 문제·공개 의존성과 신규 구현만 사용한다. 내부 Foundry 소스는 설계 참고이며 runtime import/복사하지 않는다. 추가 모델 실행·비용·외부 공유·배포는 포함하지 않는다. H24 실제 모델과 H12 실제 사람, D00/D01/D03 관문은 유지한다. 기술 판정은 harness status의 현재 입력 기준이며 이 계획 문구는 PASS 증거가 아니다.

H26~H30 구현을 검사에 연결했다. 신규 worker.scheduling(분기 한정 탐색)과 inventory.replenishment(재고 상태 동적계획), 독립 전수탐색 checker, offline profile registry, 세 도메인 MCP 및 공통 Python/Node 앱을 제공한다. 새 꾸러미의 모델 평가 8과제는 준비만 했으며 추가 모델 실행 0회다. H30 PASS 시 정확히 시험한 ZIP·소스 archive를 `.harness/work/multidomain-evaluation/`에 hash별로 보존한다. 파일 제공·외부 공유·배포 승인은 이에 포함되지 않는다.

## 2026-10-27 source publication scope

The owner confirmed company disclosure/distribution rights, patent disclosure clearance and Apache-2.0 for the reviewed GitHub source. LICENSE and notices accompany source and local builds. The repository-selection guard checks the exact public inventory; registry/release assets, site/trial deployment, operating budgets and external acceptance remain separate. D00 includes additional operating decisions and is not marked wholly PASS by this scoped source approval. Publication metadata or documentation changes expire affected harness evidence; rerun only relevant gates and report their actual scope.

H31 validates this scoped source-publication transition after H11 and H29: exact inventory and rejection tests, independent build approval, licensed fresh three-domain consumers, and local site/kit reconstruction. Remote visibility and anonymous access are verified separately after publication. It does not mark older external or hosted-trial gates PASS.

## Public GitHub first-use verification

H32 follows H31 and executes the README's actual build/install, three-domain
examples and MCP commands from a new selected-source checkout, empty HOME and
new environments. It checks generated JSON/TOML configuration against a real
multi-profile MCP session, rejects invalid inputs before execution, and exercises
the documented Node install and existing-environment recovery. Its offline
regression uses reviewed public dependency caches. Anonymous GitHub cloning and
first online downloads are recorded separately with their exact public commit;
local fixes are identified separately from that published baseline. No model
call, external-human acceptance, website deployment or registry publication is
implied. See the current harness status for results.

## Developer experience and explicit verification scope

H33 → H34 → H35 → H36 follow the existing source/onboarding gates. H33 checks
public status consistency and the documentation-only site artifact. H34 builds and
installs the Python/MCP path with Node/npm unavailable. H35 exercises worker CSV
input, explicit scenario changes, solving and comparison. H36 distinguishes
feasibility, objective recomputation and proof checks in installed app/MCP flows.
Each stage requires current predecessor PASS. Package publication, additional
model runs, external developers and new site deployments are outside these local
checks. See harness status for results; this plan is not evidence of completion.

## 2026-10-27: Site explanation and entry-path review

The owner requested local site/README improvements and review before deployment.
The public homepage now explains integration value, links directly to local and
AI setup, and retains Omelet as the recommended trial when invited. Current
profile limits and narrower engine limits are distinct; engine authoring separates
existing profiles from new domains. Routing, worker and inventory website outputs
are calculated and independently checked at build time. Public editorial content
lives in `site/content.py`; builders retain output selection and README command
extraction. Concurrent CSV analysis and verification-scope documentation were preserved.

Standalone documentation/static-artifact checks passed 14 tests; real example
costs were 18 meter, 7 cost_unit and 16 cost_unit. Eight pages were inspected at
320/390/768/1440px, including mobile menu, example keyboard tabs and exact command
copying. Workspace transfer integrity and working-file publication inventory also
passed within their stated scopes. Evidence, exact rendered files and screenshots
are local under `.harness/work/site-refresh-20261027-202020/`. This does not advance
harness dependencies, establish external acceptance or authorize publication.
No commit, push, deployment or model call was performed. The preview includes
pending local installer changes; synchronize reviewed source and documentation
before a separately authorized deployment.

## 2026-10-27: Approved source and Pages update

After reviewing the preview, the owner authorized the validated documentation and
installation changes on `omelet-ai/optimization-context-protocol` `main`, followed
by deployment to its existing GitHub Pages site. The separate scope is recorded
in `provenance/PUBLICATION_APPROVAL.md`.

Pre-publication standalone checks in an isolated selected-source copy passed
79 tests: exact README/full-kit consumers (7), no-Node Python/MCP setup (11),
worker CSV scenarios (12), dimensioned independent verification (18), existing
site/download/install regression (17), and public documentation/static artifact
checks (14). No tests were skipped and no models were called. The public build
contains 33 static files, real checked examples and no package or trial service.
Workspace transfer verification also passed for 307 copied source files; this
does not establish product or trial readiness. Source inventory and Git index
must match the 224-file allowlist before commit. Local evidence is preserved
under `.harness/work/pages-publication-20261027/`; published commit, Pages build,
fresh online install and URL results are recorded there after remote checks.
These standalone results do not promote stale harness dependencies or establish
external-human acceptance.

## 2026-10-27: Foundry-first standard convergence

The owner requested one authoritative contract, SDK and contract validator for
internal and external use, with existing Foundry work as the baseline. H37–H40
record source/mapping, standalone packages, shared SDK regressions and isolated
real Routing OCP integration. The detailed local plan is
`docs/plans/FOUNDRY_STANDARD_CONVERGENCE.md`. Existing shared Foundry checkouts are
read only; public Core 0.1 remains a separately identified compatibility lane.
Current results belong to harness evidence, not this task entry. New extracted
source/artifacts remain local and unapproved for publication. Commit, push,
deployment, paid execution and broad Foundry migration need separate approval.

The follow-up H41–H43 scopes a separately named native-contract artifact and an
opt-in native export for the complete existing Foundry candidate-consumer package.
Build, typecheck, legacy/native regressions, patch rollback and real fresh-install
execution run on isolated pinned source. Shared Foundry code, original imports,
root lock and deployed defaults remain outside this local change. Results follow
the current harness; source extraction and publication approval remain separate.

The 2026-10-28 continuation H44-H47 connects public Python/TypeScript SDK source
to the pinned native contract and uses the unchanged Foundry router/store/worker
for routing, worker and inventory reference providers. Real stdio MCP uses the
same jobs. Core 0.1 entrypoints remain available. Extraction artifacts stay local;
shared Foundry edits, commits, pushes, publication, paid/model runs are excluded.

H48-H50 continue with the native review bundle, exact documented no-Node Python
installation, generated MCP configuration and optional Node app. The existing
Core onboarding gates are refreshed through H36 before the two paths converge
at H49. H50 verifies a single-source cancellation-uncertainty proposal through
public and isolated internal consumers, including exact artifact rollback.
The proposal has a separate version; it does not silently update the pinned
Foundry authority, default artifacts, publication inventory or shared checkout.

H51-H52 extend the local candidate to three external-style engineering journeys:
independent no-Node Python installations, new synthetic business inputs, changed
conditions, valid infeasibility, actionable validation failures, saved application
results and corrupt-result rejection. Optional Node and real MCP clients reuse
the same problems. MCP replays retain the job identity and separate provider
evaluation from independent checks. These agent-run exercises do not certify
external-human adoption, other operating systems or production-scale solvers.
Results follow current harness evidence. Shared Foundry, commits/pushes, new
publication, model runs and paid resources remain outside this local scope.

## 2026-10-27: Omelet color palette preview

The owner requested purple and light green using the Omelet website as the visual
reference. The local site now uses its observed purple `#7B5BFF`, a darker
`#6443DF` accent for small text/actions, and a complementary light green `#D5F89B`.
The palette covers CSS, the OCP mark, diagrams, route illustrations and browser
theme color. Content, installation commands and protocol behavior are unchanged.

The public-edition build and nine existing artifact checks passed. Eleven
specified normal-text color combinations have contrast of at least 5.20:1;
the large purple heading has 4.19:1 contrast. Workspace transfer and source
inventory checks also passed within their existing scopes. Local evidence is
under `.harness/work/brand-palette-20261027/`. The app browser did not attach,
so rendered visual/mobile checks remain unverified. This is a local preview;
no commit, push or additional deployment was performed for this palette update.

The owner subsequently approved this palette update on `main` and GitHub Pages,
including desktop/mobile checks after deployment. The existing Chrome connection
now renders the local preview and confirms the desktop palette. The four site
source files still match the checked build; rerun the public artifact and index
checks before publishing. Deployment hashes and published viewport/contrast
results are recorded locally under `.harness/work/brand-palette-20261027/` after
execution. This approval does not include trial or package publication.

## 2026-10-27: Wider opening text preview

The owner requested a wider, more stable opening text layout. The hero copy
column now has more space and its lead uses up to 60ch; capped desktop padding
keeps the title from rewrapping on very wide screens. At 1440px, copy width is
601px (previously 540px), the lead is 601px (previously 480px), and the unchanged
82px heading occupies three lines. Chrome checks at 11 widths from 320 to 2560px
found no page overflow; 320px retains natural wrapping. Nine existing static
artifact checks and 307-file workspace transfer verification passed within their
scopes. Only the stylesheet differs in the reused public preview artifact. Local
evidence is under `.harness/work/hero-width-20261027/`; this update is uncommitted
and undeployed and does not advance stale harness dependencies.


## 2026-10-28: 기존 Foundry 무변경 원칙과 H53–H55

사용자는 기존 Foundry 저장소를 절대 수정하지 말라고 명시했다. 기존 checkout,
연결된 worktree, Git index/refs/config를 포함하며 worktree 등록과 fetch도 하지 않는다.
별도 Git 메타데이터를 가진 임시 bare clone에서 고정 main을 읽고 선택 파일만
복사한다. 원본 inventory는 GIT_OPTIONAL_LOCKS=0으로 읽으며, 실제 실행은 모든
등록 worktree/Git 디렉터리 쓰기 차단과 실행 전후 hash 비교를 동반한다.

| 단계 | 선행 | 검증 범위 |
| --- | --- | --- |
| H53 | H52 | 원격 main acbc2d6f368e 고정, 공통 계약/SDK/전체 consumer 동일성 확인, 독립 복사본 opt-in build/typecheck/legacy/native 회귀와 patch rollback, 현재 실제 Routing API 실행 및 검산 |
| H54 | H53 | 고정 공개 Python Docker 이미지, Linux amd64 emulation, 새 HOME/venv, Node 없음, offline 설치, 세 도메인의 정상/변경/불가능/단위 오류를 앱과 실제 MCP로 실행 |
| H55 | H54 | 정확한 bundle ZIP/hash, 계약 소스 권리 검토 목록, 실행 가능한 등록 template, 독립 사용자 과제/평가표, 9개 합성 모델 과제와 실행 상한의 준비 검사 |

기존 canonical pin 7547036d1bc9와 공개 224-file 목록은 유지한다. 현재 main의
선택 파일 중 5개 엔진/metadata 변경은 H53에서 별도로 실행 검증하며, 정본의
조용한 갱신이나 회사 전체 채택을 뜻하지 않는다. 취소 불확실성 수정 제안은 H50의
별도 review 버전이며 upstream 반영을 주장하지 않는다.

외부 참여자가 아직 없다는 사용자 답변에 따라 사람 시험은 PREPARED/NOT_RUN이다.
모델 9개 과제는 각 1회, 재시도 0, 새 job 총 6개 이하, 시도당 120초로 제안하며
실제 추가 모델 실행 승인은 별도다. H55 PASS는 준비 검사만 뜻한다. 과거 H24의
Core 모델 결과를 native 결과로 옮기지 않는다. 새 추출 소스 권리, 정확한 commit/push,
패키지·사이트·외부 공유/배포는 승인 전 실행하지 않는다.

## 2026-10-28: Core/native documentation and wider hero publication

The owner authorized README/site guidance distinguishing public Core 0.1 from
the local, unpublished native v1 candidate, including formats, SDK entrypoints,
six versus eight MCP tools, real job lifecycle and compatibility boundaries.
The protocol comparison table is rendered from README. Native implementation,
extracted packages and review bundles remain outside the public inventory.
The approved hero layout increases the desktop text measure and preserves
responsive wrapping. Build, source inventory, command/table consistency, links
and browser checks are recorded against the exact artifact in local evidence.
Commit/push targets `main` and the existing Pages `gh-pages` branch only.
Existing Foundry repositories are not modified. These documentation checks do
not promote stale harness stages or establish native publication or acceptance.


## 2026-10-28: 승인된 native 모델 시험과 평가 출처 수정

사용자가 기존 Codex 계정으로 native 합성 과제 9개를 각 1회 승인했다. 고정된 준비 꾸러미로 실제 MCP 호출·답변을 실행하고 원문·사용량·서버 감사 기록은 비공개 증거에 보관한다. 재시도·대체 과제·추가 모델 호출은 하지 않는다. 이 제한 시험은 독립 외부 개발자 수락이나 수정본의 모델 재시험을 대신하지 않는다.

시험 중 발견한 라우팅 제공자 평가의 `independent` 출처 표기를 `engine`으로 바로잡고, 별도 checker와 제공자 내부 재평가의 차이를 명시했다. 해가 null이면 evaluate를 호출하지 않도록 native MCP 안내를 보강했다. 불가능 사례에서 평가를 필수 호출로 요구하던 준비 평가표도 수정했다. 실제 거절 응답과 최초 판정 기록은 보존한다. 계약 형식과 Foundry 정본은 변경하지 않으며 관련 하네스로 새 빌드의 회귀를 확인한다. 기존 Foundry checkout·worktree·Git 메타데이터 무변경 원칙, 커밋·푸시·공유·게시 보류를 유지한다.


## 2026-10-28: H56 독립 BYO 워커 엔진과 같은 앱 교체

H55 다음 단계로 H56을 추가한다. `authoring/worker_greedy/`에 기존 워커 솔버를
호출하지 않는 시간순 탐욕 배정 엔진과 별도 Core provider를 구현한다. 공통 SDK와
`worker.scheduling@0.1.0` 스키마, native router/job/MCP 구조만 재사용하며, Foundry
정본·기존 저장소는 수정하지 않는다. 별도 wheel을 새 HOME/venv에 오프라인 설치하고
같은 앱의 등록 지점만 바꿔 발견→검증→실제 job→결과→독립 검산까지 확인한다.

H56은 80개 고정 난수 사례와 별도 전수탐색 oracle, 5개 제약/비용/해 변조 탐지,
실제 MCP, reference/checker import 차단 프로세스를 검사한다. 참조 엔진 비용 3과
탐욕 엔진 비용 101의 차이, 해가 존재해도 탐욕 엔진이 `unknown`인 반례를 포함한다.
BYO가 찾은 해는 `feasible`, 미발견은 `unknown`이며 최적성·불가능 증명을 만들지
않는다. 공통 계약 호환은 해 품질의 동일성이나 전체 엔진 인증이 아니다.

독립 구현과 외부 독립 저작자를 구분한다. 이 예제는 같은 개발 작업에서 작성한
두 번째 알고리즘의 기술 검증이며 실제 외부 개발자 수락은 여전히 NOT_RUN이다.
추가 모델 실행·비용·커밋·푸시·외부 공유·게시·배포는 별도 승인 전 수행하지 않는다.
명령과 검증 범위는 `docs/users/NATIVE_BYO_WORKER.md`에 기록한다.

## 2026-10-28 native source publication approval

The owner approved rights, Apache-2.0 and patent disclosure for the 28 extracted
sources, final notices, the reviewed 301-file candidate on main, and matching
README/GitHub Pages updates. Six package notice files finalize the 307-file
selection. The independent source checks and installed-runtime checks apply to
this candidate; historic harness stages are not promoted. Concurrent BYO worker
work and existing Foundry repositories are excluded. See
[publication scope](provenance/PUBLICATION_APPROVAL.md).


## 2026-10-28: H57–H58 독립 profile 확장과 교차 검증

H56 이후에는 내장 도메인을 복제하지 않고 별도 설치 패키지로 새 문제를 추가한다.
H57은 `example.budget-selection@0.1.0`의 schema 패키지, 동적계획법 솔버,
독립 부분집합 검산기를 각각 설치한다. 공통 `ProfileRegistry`와 명시적
`Extension`/`CheckerRegistry` 등록만 사용한다. 공통 앱·MCP·SDK·native router/job
소스를 도메인별로 수정하지 않는다. `total_cost` 대신 효익 최대화 목적을 사용해
범용성을 검사한다. 빈 해의 0과 해 없음의 null, 시간 제한의 feasible과 optimal을
구분하며 80개 고정 난수·변조·등록 충돌·버전 오류·독립 import 검사를 포함한다.

H58은 같은 입력을 macOS arm64 Node SDK와 네트워크를 끈 Linux amd64 Python·MCP로
실행한다. BYO 워커와 reference의 같은 해·품질 차이·휴리스틱 미발견·불가능·단위
오류, 새 profile의 정상·예산 변경·0·단위 오류까지 상태와 목적값을 비교한다.
Linux는 Docker emulation이며 Windows·Linux Node·native Linux arm64는 검증하지 않는다.
H57→H58 순서로 현재 PASS를 확보하며 이전 게이트가 만료되면 현 소스로 갱신한다.

이는 로컬 등록 API 0.1.0 추가이며 Core 0.1/native v1 wire와 Foundry pin은 유지한다.
기존 서버는 확장을 설치해도 자동 활성화하지 않는다. host가 지정한 설치된 factory만
실행하며 LLM/문제/catalog에 실행 코드 선택권을 주지 않는다. checker는 정확한
profile 버전·목적 metric·검산 범위·자기 identity를 명시하며 등록만으로 인증되지 않는다.
Foundry 기존 checkout·worktree·Git 메타데이터는 쓰기 차단과 전후 해시로 보존한다.
이번 예제/후보 꾸러미는 동시 진행된 native 소스 공개 승인에 포함하지 않는다.
추가 모델·외부 개발자 수락·commit/push·공유·배포·유료 실행은 별도 승인 대상이다.


## 2026-10-29: H59–H60 독립 프로젝트 적용 흐름

H58 이후 새 프로젝트 생성→독립 설치→입력 변경→같은 앱의 엔진 교체→실제 native
job/MCP→독립 검산→기록 재검토를 하나의 작업 흐름으로 제공한다.
`examples/native/project.py`는 교체 가능한 앱 예제이며 Core/native wire나
Foundry 정본의 새 필수 계층이 아니다. 입력/config/기록에서 실행할 factory를
불러오지 않고 host가 명시적으로 선택한 설치 패키지만 사용한다.

H59는 macOS 새 HOME/venv와 별도 프로젝트 폴더에서 라우팅·워커·재고 및
BYO·새 profile을 실행한다. 워커 근무시간 변경의 비용 7→9, heuristic unknown과
증명된 infeasible의 null, 출력 덮어쓰기 거부, 실제 stdio MCP, 변조된 해/요약/
job identity 거부를 확인한다. 제출 전에 key를 기록하고 불확실한 응답은 자동
재시도하지 않는다. 저장된 PASS 대신 별도 checker로 원래 요청·결과를 재검산한다.
H60은 네트워크 없는 Linux amd64 emulation에서 같은 문서 명령과 실패 회귀를
검사한다. 장애 주입 검사는 실제 외부 네트워크 장애 실적과 구분한다.

이 검증은 기존 H53 내부 모듈 적용 리허설에 독립 프로젝트 운영 흐름을 더한다.
기존 Foundry checkout/worktree/Git 메타데이터 무변경과 전후 hash 검사를 유지한다.
공통 계약 pin 7547036d1bc9, 후속 내부 리허설 pin acbc2d6f368e는 유지하며 현재
checkout 또는 최신 원격 main 전체 일치로 표현하지 않는다. Gateway/ocps1/Studio
전체 제품 수렴은 별도 범위다. 실제 내부 owner 수락과 외부 독립 개발자 시험은
`ADOPTION_REVIEW.json`에 NOT_RUN으로 남고 자동 검사로 바꾸지 않는다.
추가 모델 실행·비용·커밋·푸시·공유·게시·배포는 승인 전 수행하지 않는다.


## 2026-10-29: H61–H62 고정 시간 점검 업무 수락 준비

사용자가 선택한 고정 시간 점검 작업 배정을 첫 합성 내부 적용 후보로 만든다.
H61은 작업자 3명·점검 6개의 CSV→표준 worker.scheduling 입력→같은 native v1
job/MCP→독립 검산→배정표·작업자 부하 보고서 흐름을 새 HOME/venv에서 검사한다.
CSV 오류는 파일·행·필드를 표시하고 알 수 없는 열·참조·중복·단위 변환을 묵인하지
않는다. 기준 비용 16, 작업량 축소 19, 가용시간 축소 25, 자격 누락의 infeasible과
BYO unknown을 구분한다. 보고서는 저장된 PASS를 믿지 않고 다시 검산한다.
H62는 같은 안내 명령과 입력/변조 회귀를 네트워크 없는 Linux amd64 emulation에서
반복한다. Node나 추가 LLM 없이 실행한다. Core/native wire/Foundry pin은 바꾸지
않으며 CSV와 보고서는 교체 가능한 업무 앱이다. 내부 공유 Foundry에 쓰지 않는다.

수락 안내는 `docs/users/NATIVE_INSPECTION_ACCEPTANCE.md`에 둔다. 자동 검증은
실제 내부 담당자의 업무 적합성 수락을 대신하지 않는다. 생성된 OWNER_REVIEW.json과
외부 개발자 수락은 NOT_RUN으로 남긴다. 이동·휴식·공정성·노동 규칙·불확실성은
미지원이며 실제 업무에 필요하면 적합성 실패로 기록해야 한다. 새 꾸러미는 로컬
검토용이다. 커밋·푸시·외부 공유·배포·추가 모델 실행·비용은 별도 승인 대상이다.


## H63: 최초 프리릴리스 준비

- 버전·지원 범위·승인 분리: `docs/development/preview-release.json`.
- 선택 소스/설치 ZIP·해시·빈 사람 검토 양식: `tools/prepare_preview.py`.
- 동일 추출 ZIP의 macOS Python/Node 및 오프라인 Linux Python/MCP 실제 회귀: `tools/check_preview_candidate.py`.
- Foundry 원본과 등록 worktree는 수정하지 않고 기존 H00–H62 로컬 경로를 먼저 갱신한다.
- 이 단계의 PASS는 준비물과 자동 검증 범위에 한정한다. 사람 시험·게시 이력은 생성하지 않는다.

## H63 follow-up: first-user scenarios and approved delivery

- Add installed regressions for wrong Python, dependency timeout without retry,
  partial-environment preservation, malformed manifest, a Unicode/spaced install
  path outside the current directory, actionable CSV corrections, and independent
  adjacent/overlapping task scenarios. Run them on macOS and offline Linux.
- Separate the prerelease ZIP path from source development in README and Pages;
  preserve checksum, version, no-key MCP and explicit preview limits.
- Publish only checked selected source/assets under the 2026-10-29 scoped
  approval; anonymously redownload and run after delivery. Completed logs remain
  private. External-human/internal-owner acceptance and registry/model trials
  remain separate; Foundry original repositories remain unchanged.

## H64: public-source CI and explicit platform boundaries

Build one read-only workflow for public macOS/Linux Python and optional Node,
plus Windows unsupported-platform diagnostics. `tools/check_public_ci.py` uses
only selected source in a new directory, a fresh build environment, real
three-domain jobs/MCP and independent checker/inspection regressions. It does
not require or promote private Foundry migration evidence. H64 is an independent
development branch after H00, not a rerun or automatic promotion of H63's
immutable published kit. Its check output binds the actual source and kit hashes.

The workflow source/policy tests are local preparation. Hosted workflow execution,
repository branch protection, source push and further publication are separate
actions. Configure native Linux/Node as a target; claim support only after the
actual lane passes. Windows remains unsupported. Existing Foundry repositories
are never modified; no model calls or human acceptance are inferred. See
[Public CI](docs/development/PUBLIC_CI.md).


## H65: public onboarding and independent agent rehearsal

H65 follows the current H64 public-source installation gate. README and the
public site recommend the immutable native ZIP for a first run, share checksum
and install/MCP commands, and distinguish its original acceptance from newer
macOS/native Linux source CI. Ten minutes is an estimate after Python setup,
not a measured human success rate. Optional Node commands are executed from the
kit documentation so filename drift cannot hide behind manifest-based tests.

Three fresh-context agents independently rehearse public ZIP usage, app/engine
integration and MCP semantics with synthetic inputs. Their findings guide fixes
and reproducible regressions; raw evidence remains private. These are agent
simulations, not external-human or model-host acceptance. Existing Foundry is
write-protected. Commit/push, Pages updates, replacement release assets, package
registries and additional model trials remain separately scoped actions.

Rehearsal regressions cover missing worker costs with actionable field paths,
malformed/duplicate/non-finite MCP input rejected before any client starts, and
MCP job states/response shapes derived from the shared native contract. The
immutable published ZIP remains unchanged; its Node filename correction is
documented in the current README/guide and exercised in newly built kits.
