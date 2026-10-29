# OCP 개발 하네스

단계와 진급 조건을 [plan.json](plan.json)에 정의한다. 내부 자율 개발 계획은 로컬 원본 보유 공간의 `docs/plans/`에 별도로 보존한다. 제품 독립 적합성 검사인 `conformance/`와 이 개발 실행기를 구분한다.

H00은 원본 이관 무결성까지 확인하는 로컬 개발 관문이다. 원본 snapshot·이관 목록을 제외한 Git clone에서는 H00을 실행해도 통과하지 않는다. 이를 skip·가짜 PASS로 대체하지 않는다. clone의 새 구현·build·소비자 검사는 [독립 검사 안내](../docs/development/LOCAL_RUNTIME.md)대로 직접 실행할 수 있으며 원본 이관 검증과 구분한다. 실제 외부 관문의 선행 조건은 그대로 유지한다.

```sh
python3 -B tools/harness.py validate
python3 -B tools/harness.py status
python3 -B tools/harness.py next
python3 -B tools/harness.py run H00
```

모든 명령은 프로젝트 루트에서 실행한다. 실행기 자체는 Python 3.9 이상과 표준 라이브러리를 사용하고 제품 검사는 [고정된 개발 환경](../docs/development/LOCAL_RUNTIME.md)을 사용한다. 동일 환경에서 run/status를 호출한다. 현재 실행 가능한 단계는 plan.json의 checks로 확인하며 검사 없는 단계는 자동 통과하지 않는다. `validate`의 PASS는 계획 구조만 확인한다. `status`와 `next`의 종료 코드 0은 조회 성공이며 제품 PASS가 아니다. `run`은 단계 PASS에만 0, 검사 실패·만료에 1, 실행 불가·정의 오류에 2를 반환한다.

## 검사 추가

H25는 H23 뒤 no-key MCP 통합 설치·진단·실제 stdio 계산/독립 검산·Python/Node 소비자와 로컬 평가 꾸러미를 검사한다. `tools/check_kit_environment.py`는 정확한 ZIP을 새 HOME·venv·npm cache에서 재현하는 별도 도구다. 같은 ZIP의 macOS/Linux 실행은 각 보고서의 platform·machine·hash로 식별하며 Docker emulation을 native Linux로 표현하지 않는다. H24 실제 모델 수락과 H12 사람 시험은 별도다. [평가 준비 절차](../docs/development/NO_KEY_EVALUATION.md)를 따른다.

단계별 acceptance를 충족하는 코드·fixture·검사기를 먼저 구현하고 해당 단계의 `checks`에 명령을 연결한다. 명령은 shell 문자열이 아닌 argv 배열이며 `{python}`은 현재 Python 실행기로 바뀐다. 검사기는 stdout에 JSON 객체 하나를 출력한다. 필수 검사 실패는 0이 아닌 종료 코드를 반환한다.

`expect`는 정확한 타입과 값을 검사하고 `status: PASS`가 필수다. 테스트 실행에는 `min_tests`를 양수로 정하고 실행·실패·오류·skip 수를 보고한다. 필수 테스트가 0개이거나 skip됐다면 통과하지 않게 정의한다. 실제 기능 검증 없이 JSON PASS만 출력하는 검사는 허용하지 않는다.

`inputs`에 계약·구현·fixture·checker·lock 파일 등 결과에 영향을 주는 소스를 모두 연결한다. 공유 하네스 정의와 코드, 각 선행 보고서도 hash에 포함된다. 입력 밖의 외부 API·설치 artifact·브라우저·engine 상태는 해당 단계의 검증기에서 별도로 식별하고 확인해야 한다. 빌드·보고서 출력은 입력 경로에 두지 않는다.

## 보고서와 안전한 실패

`.harness/runs/`에는 실행마다 새 보고서를 남긴다. 실행 중에는 INCOMPLETE, 완료하면 최종 결과를 저장한다. 과거 완료 보고서를 덮어쓰지 않는다. 마지막 보고서가 실패·중단·손상됐다면 더 오래된 PASS를 사용하지 않는다. 서로 다른 실행이 동시에 쓰지 않도록 `.harness/run.lock`을 사용한다. 강제 종료로 lock이 남으면 PID와 실제 프로세스 종료를 확인한 뒤 해당 lock만 정리한다.

현재 검사는 환경변수를 제한해서 전달하고 stdout/stderr 원문 대신 hash를 저장한다. 실패한 명령과 이유·종료 코드는 보고서에 남는다. 상세 원인 확인이 필요하면 에이전트가 해당 명령을 직접 재실행하며 비밀·실데이터를 보고서에 추가하지 않는다. 외부 서비스 credential 전달·외부 승인 증거 검증은 현재 구현하지 않았다.

검사기의 확인된 test 수·실패/오류/skip 수·scope·artifact SHA-256·versions만 보고서의 `verified_report`에 남긴다. 임의 출력 payload와 로그 원문은 포함하지 않는다. 제품 버전과 검사 범위를 확인할 때 이 필드를 사용한다.

이 실행기는 승인 우회 기능, 자동 게시·배포, 백그라운드 개발, 사람이 실제 과제를 완료했다고 판정하는 기능을 제공하지 않는다. 외부 단계는 검증기와 실제 출처가 준비될 때까지 WAITING_EXTERNAL 또는 선행 BLOCKED로 남는다.

`decision` 모드는 이미 받은 결정의 원문 출처와 정확한 scope를 모두 검사하는 D 단계에만 사용한다. D02는 로컬 원래 user message와 보존한 receipt를 대조하며, 현재 승인 범위는 Foundry의 지정 branch에서 최소 소비자 구현·검사·commit/push/draft PR까지다. 단순 `status: PASS`, 승인 boolean 또는 assistant의 재인용으로 대체할 수 없다. 해당 로컬 원문이 없으면 실패하며 다른 환경에 receipt를 복사해 새 권한을 부여하는 기능이 아니다. 이후 사용자 변경 지시가 우선한다. D00/D01/D03은 여전히 외부 결정 대기다.

H11의 DX 계측 검사는 시간·지원·재시도·자동 실행 제외 규칙만 확인한다. [외부 과제지](../docs/users/EXTERNAL_DX_STUDY.md)의 실제 참여자·신원·동의·독립 활용을 증명하지 않으며 H12를 자동 통과시키지 않는다.

H15~H17은 [좌표/실제 로컬 연결 결정](../docs/decisions/0003_COORDINATES_AND_LOCAL_TRIAL.md)에 따른 독립 기술 후보다. H16/H17은 명시적으로 승인된 loopback 설정과 실제 엔진을 요구하며 환경이 없으면 실패한다. H08/H09 및 D00/D01의 전체 외부 운영 조건은 유지한다.

H18은 [catalog 호환성 결정](../docs/decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md)에 따른 로컬 소비자 검사다. H17·D02의 현재 PASS, 기록된 main 기반 실제 API, source identity와 private client package hash를 요구한다. 이전 1.4.0 실제 경로도 검사하며 H10을 자동 승격하지 않는다.

H04가 실패하면 검사 번호·실패 유형·소요시간을 제한된 `failure_diagnostics`로 남긴다. 하네스는 허용된 숫자·분류만 보존하고 원문 로그·예외 메시지·입력·자격 증명은 저장하지 않는다. 진단 정보는 PASS 근거가 아니며 nonzero exit는 계속 FAIL이다. 자동 재시도로 실패를 덮어쓰지 않는다.

H19는 [초대 운영 준비](../docs/decisions/0005_INVITATION_PREPARATION.md)를 검사한다. H07/H11/H18 선행 후 운영/장애 회귀와 설치된 MCP-only client→실제 로컬 Foundry를 확인한다. 사용자 담당 배정은 기록했으나 D00 전체 권리 검토와 D01 실제 외부 경로, Claude Code host 및 외부 참여자 수락은 별도다.

H20은 H19 이후 새 설치 꾸러미에서 U01~U09 사용성 회귀를 검사한다. Node/npm은 PATH, cache는 OCP_NPM_CACHE, offline 모드는 OCP_NPM_OFFLINE=1로 명시한다. 첫 온라인 준비는 [소스 빌드 안내](../docs/development/BUILD_FROM_SOURCE.md)를 따른다. 자동 소비자 검사는 실제 외부 사람이나 Claude Code host 수락이 아니다.

H21은 H11/H20 뒤에 [사이트 로컬 후보](../site/README.md)의 명시 출력·링크·꾸러미 해시와 사이트에서 내려받은 새 설치·실제 Python/Node/BYO 실행을 검사한다. 브라우저 렌더링·상호작용은 별도 관찰이며 H21 자동 PASS가 이를 대신하지 않는다. 공개 사이트 게시와 실제 외부 개발자 수락도 별도다.

H21 예제는 새 설치에서 엔진 준비(60초)와 준비 후 실행(30초)을 구분하며 solve 예산 1,000ms는 유지한다. 실패 진단은 고정된 `site_engine_startup`/`site_example_execution`과 숫자 상한만 추가 보존한다. 재시도나 미리 로딩한 엔진으로 첫 실행 실패를 가리지 않는다.

H22는 H21 뒤 새 꾸러미의 한 명령 첫 성공, 동일 앱·입력의 두 실제 라우팅 엔진, 별도 설치한 checker의 변조 탐지, deadline 의미와 실패 복구를 검사한다. `python3 -B tools/harness.py run H22`를 사용한다. 일반 엔진 인증·실제 사람 수락·Linux/Windows·비라우팅 실행은 범위에 포함하지 않는다.

H04도 실제 backend 생성 시점의 준비 신호를 사용한다. cold 준비 60초와 준비 후 App A 실행 15초를 분리하고 `app_engine_startup`/`app_example_execution` 실패 단계만 기록한다. H21과 같은 단일 프로세스 감시를 재사용하며, 최초 실행 재시도나 결과 성공 대체를 하지 않는다.

H23은 H22 뒤 실제 설치 MCP의 컨텍스트 제공, tools-only 소비, 올바른 요청·실제 결과·오류 의미와 모델 시험 꾸러미를 검사한다. `tools/check_h23.py`는 모델을 호출하지 않는다. H24는 새 대화의 실제 LLM 도구 사용·질문·최종 답변과 사용량을 추적하는 외부 단계다. 모델·호스트·합성 자료 전송·사용량 범위가 결정되기 전에는 실행하지 않으며 준비물이나 SDK 성공을 외부 PASS로 바꾸지 않는다. [검증 방법](../docs/development/LLM_CONTEXT_VALIDATION.md)을 따른다. 승인된 첫 모델 시험의 상세 기록은 비공개 증거로 보관한다. 호스트 설정 실패도 시도로 집계하고, 수정 후 모델 재시험은 별도 사용량 승인 범위를 따른다. H05는 분석적 불가능 증명의 수치 변조도 거부해야 한다.

## 2026-10-27: 세 도메인 실제 실행 확대

사용자가 워커 스케줄링과 재고 발주 profile·실제 solver·독립 checker 및 공통 앱/MCP 구현을 승인했다. 기존 두 번째 도메인 fixture 범위를 확장하되 assignment.fixture와 Core 의미는 유지한다. H26 계약 → H27 워커 → H28 재고 → H29 공통 앱/MCP → H30 새 설치·평가 준비 순서이며 각 현재 선행 PASS 후 진급한다. 작은 합성 문제·공개 의존성과 신규 구현만 사용한다. 내부 Foundry 소스는 설계 참고이며 runtime import/복사하지 않는다. 추가 모델 실행·비용·외부 공유·배포는 포함하지 않는다. H24 실제 모델과 H12 실제 사람, D00/D01/D03 관문은 유지한다. 기술 판정은 harness status의 현재 입력 기준이며 이 계획 문구는 PASS 증거가 아니다.

H26~H30은 [세 도메인 결정](../docs/decisions/0008_MULTI_DOMAIN_REFERENCE.md)을 따른다. H27 워커 search와 H28 재고 DP는 독립 전수탐색 정답에 대조한다. H29는 실제 MCP 한 프로세스의 세 profile 및 동일 Node 앱을, H30은 새 ZIP·HOME·venv와 solver-free checker를 검사한다. H30이 통과하면 시험한 artifact를 `.harness/work/multidomain-evaluation/<ZIP SHA-256>/`에 보존한다. 추가 모델 과제는 준비만 하며 H24/사람/게시 관문을 통과시키지 않는다.

## 2026-10-27 source publication scope

The owner confirmed company disclosure/distribution rights, patent disclosure clearance and Apache-2.0 for the reviewed GitHub source. LICENSE and notices accompany source and local builds. The repository-selection guard checks the exact public inventory; registry/release assets, site/trial deployment, operating budgets and external acceptance remain separate. D00 includes additional operating decisions and is not marked wholly PASS by this scoped source approval. Publication metadata or documentation changes expire affected harness evidence; rerun only relevant gates and report their actual scope.

H31 validates this scoped source-publication transition after H11 and H29: exact inventory and rejection tests, independent build approval, licensed fresh three-domain consumers, and local site/kit reconstruction. Remote visibility and anonymous access are verified separately after publication. It does not mark older external or hosted-trial gates PASS.

H32 executes the marked README command blocks from selected source in a fresh
home/environment, including three-domain apps, no-solve context discovery,
generated multi-profile MCP configuration, actual tools, invalid inputs and
Node installation. `tools/check_h32.py` uses reviewed offline dependencies; it
does not claim a GitHub download or a human's unaided success. Record a separate
anonymous public-clone/online rehearsal before making those claims. H31 must be
current PASS before H32 can advance. Neither gate calls a model or publishes a
package/site.

## Developer experience and explicit verification scope

H33 → H34 → H35 → H36 follow the existing source/onboarding gates. H33 checks
public status consistency and the documentation-only site artifact. H34 builds and
installs the Python/MCP path with Node/npm unavailable. H35 exercises worker CSV
input, explicit scenario changes, solving and comparison. H36 distinguishes
feasibility, objective recomputation and proof checks in installed app/MCP flows.
Each stage requires current predecessor PASS. Package publication, additional
model runs, external developers and new site deployments are outside these local
checks. See harness status for results; this plan is not evidence of completion.

H37 → H38 → H39 → H40 is the Foundry-first convergence lane. Its pinned native
contract is independent of the older public Core 0.1/trial lane. H37 verifies the
source mapping and checkout boundaries after H00. H38 packages unchanged Foundry
contract validators, H39 exercises the unchanged shared SDK, and H40 installs the
same artifacts in an external-style app and an isolated real internal Routing OCP
module against the actual local Routing API solver. It does not change shared
Foundry checkouts, certify all domains, advance H10, or authorize publication.
The local plan is `docs/plans/FOUNDRY_STANDARD_CONVERGENCE.md`; source pin and
reproducible tooling are in `tools/foundry_convergence/`. New extracted sources
and artifacts remain excluded from the public selection pending scoped review.

H41–H43 continue that lane with a distinct native-contract package, an opt-in
`./native` export in an isolated copy of the complete Foundry candidate-consumer
project, and fresh installed internal/external consumers against the real engine.
The original consumer entrypoint and source remain compatible. Node 22 project
checks, exact import-rebinding provenance and patch rollback are required. No
shared Foundry package replacement or repository/registry publication is implied.

H44-H47 extend the pinned lane to public Python/TypeScript SDK native entries and
a common three-domain server. Installed Foundry router/store/process workers run
real jobs and preserve domain payload semantics. H46 uses actual stdio MCP with
no model execution; H47 checks the original pinned Routing API. Existing Core
0.1 entrypoints remain available. Publication and shared Foundry edits are separate.

H48 runs the native review bundle's documented commands in a fresh environment
with no Node on the Python/MCP path, then checks the optional Node consumer.
H49 requires both H48 and the refreshed Core onboarding chain through H36;
its inventory check does not authorize newly extracted source publication.
H50 reproduces cancellation uncertainty in the pinned SDK, applies one proposal
to isolated canonical source, installs a distinct version through both public
and complete internal consumers, runs the real Routing API, and restores the
exact baseline packages/lock. Expected failing counterexamples in baseline and
rollback are reported separately from candidate success. No model or shared
Foundry mutation occurs; upstream adoption is still a separate decision.

H51 follows H50 and installs the exact native review kit independently for three
domain personas. Documented commands apply new synthetic problems, change their
conditions, retain mathematical result states, reject invalid units/JSON, save
app-consumable output and catch corrupted costs/solutions with the installed
independent checker. H52 uses those same installed artifacts for real stdio MCP
context → requirements → validation → jobs → results → evaluation and replay.
No source checkout/configuration is exposed to these subprocesses; Python works
without Node. Optional Node clients run the changed problems too. These are local
agent-operated tests on macOS, not external-human, Linux/Windows or LLM evidence.


H53–H55는 기존 Foundry 저장소 무변경을 전제로 현재 main의 독립 복사본 적용,
Linux amd64 오프라인 설치·실제 세 도메인 앱/MCP, 외부 평가 준비를 검사한다.
H53은 현재 source pin과 선택 hash가 다른 경우 중단한다. H54는 검토된 Docker
이미지와 wheelhouse가 없으면 실패하며 skip으로 통과하지 않는다. H55의 준비 PASS는
외부 참여자나 LLM의 수락이 아니다. 실제 사람 시험은 참여자 미정으로 NOT_RUN이다.


H56은 H55의 현재 PASS 후 독립 BYO 워커 엔진을 검사한다. 새 환경에서 선택 wheel을
설치하고 같은 앱의 엔진만 바꾸며 실제 native job과 MCP, 별도 checker로 검증한다.
탐욕 미발견은 unknown, 완전 해는 feasible로만 보고한다. 참조 솔버/checker import
차단, 80개 고정 난수 사례, 해·비용·제약 변조, 품질 차이와 탐욕 반례를 포함한다.
이 PASS는 외부 개발자의 독립 저작·사용 수락이나 공개 게시 승인이 아니다.


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


## 2026-10-29: H63 최초 프리릴리스 후보 고정

H62 현재 PASS 뒤 H63을 실행한다. 공개 선택 소스로만 만든 `v0.1.1-preview.1` 후보 ZIP을 해시로 고정하고, 실제 추출한 동일 파일을 macOS Python/Node·오프라인 Linux amd64 Python/MCP에 새로 설치한다. 세 도메인과 점검 CSV·독립 검산·오류 거절을 재현한다. 원래 Foundry checkout/worktree/Git metadata는 쓰기 차단과 전후 조회로 보호한다. 설치 꾸러미에는 안내·합성 입력·빈 수락 양식만 포함하며 실행 증거는 비공개 영역에 둔다.

[프리릴리스 안내](../docs/development/PREVIEW_RELEASE.md)의 계획은 게시 승인이 아니다. 레지스트리 보호 표시를 유지하고, 사람 시험 NOT_RUN·추가 모델 실행 0·미게시 상태를 명시한다. 로컬 개발 검사와 기존 외부 게이트를 임의 병합하지 않는다.

## H64: public CI implementation

H64 follows the current H00 baseline on an independent local development branch.
It runs CI-policy negative tests and the public-source checker using local
dependency stores. It verifies selected-source installation and actual consumer
execution; it does not imply a hosted GitHub run or regenerate H63 release
acceptance. The public workflow runs this independent checker directly without
H00 or any private snapshot. See [scope and reproduction](../docs/development/PUBLIC_CI.md).
