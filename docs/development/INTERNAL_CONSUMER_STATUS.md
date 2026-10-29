# Minimal internal consumer candidate

상태 확인: 2026-10-27. [Foundry PR #428](https://github.com/omelet-ai/oi-foundry/pull/428)은 2026-10-26 merge되었다. merge commit은 `87e5bec6b475770605d5d82eb9f936df3a70e3d5`이며 확인한 main `7547036d1bc9464d6c43a9bdf7cff0a78e8560d7`에 포함된다. 아래 시험 실적은 당시 head `4528ccac2b383e10e4dd3315bd2b31540d7fc272`와 base `e5ec396605221b59d05bb6a6309d95bf734e3771`의 기록이다.

사용자는 Foundry main에서 별도 worktree와 위 branch로 최소 연동을 구현하고 하네스 검증 후 commit/push/draft PR 생성까지 승인했다. 그 범위는 이미 수행했으며 재승인을 요청하지 않는다. 외부 trial 담당자·환경·예산은 별도 결정으로 남겼다. 승인 원문과 세부 증거는 로컬 비공개 기록에 보존한다.

## 구현과 확인 범위

- Studio의 인증된 로컬 preview에서 한 `routing.coordinates@0.1.0` 후보를 조회·설정·실행·평가한다. production은 거절하며 자격 증명은 서버에만 둔다.
- TMS Builder는 같은 private client package의 공개 entrypoint로 capability/requirements를 resolve한다. 기존 native release lock 경로는 유지한다.
- 신규 consumer 검사 20개, TMS Builder 136개, 기존 계약 335개, Next production build, 정상 commit/push hook을 통과했다. [PR Fast Gate](https://github.com/omelet-ai/oi-foundry/actions/runs/40175449104)도 성공했다.
- 깨끗한 환경에 설치한 package와 실제 OR-Tools/로컬 Omelet 두 provider, 독립 Python checker, 브라우저→Studio→엔진 왕복을 검사했다. 응답 `feasible`을 `optimal`로 바꾸지 않았다.

## 남은 범위

| 항목 | 현재 한계와 다음 동작 |
| --- | --- |
| 기록된 main provider | 검증 base의 catalog 1.3.0을 명시적으로 선택하는 OCP adapter와 H18을 추가했다. native engine source를 변경하지 않고 설치된 private client·기존 TMS resolver의 실제 실행과 독립 평가를 검사한다. 최신 결과는 하네스를 따른다. [호환성 결정](../decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md)에 따라 이 좁은 연동에 native provider migration은 필수가 아니다. 이전 Studio 브라우저 증거의 provider는 1.4.0이다 |
| Foundry 전체 검사 | 변경 범위 검사는 통과했지만 전체 Studio 하네스는 기존 security audit 정책에서 중단된다. 같은 manifest/lock의 base·branch 비교 결과는 같다. 전체 workspace 검사에는 main에서 재현한 Inventory assertion 실패 2개가 있다. 이를 전체 PASS로 표시하지 않는다 |
| merge와 제품 반영 | main에 merge되었지만 opt-in 좌표 preview와 TMS discovery 범위다. native wire contract의 통일·기본값 전환·제품 배포를 뜻하지 않는다 |
| OCP H10 | H09와 D02가 선행한다. 최소 연동의 구현·승인 사실과 H10의 전체 PASS를 구분한다. H09 외부 trial이 완료되기 전에 H10을 올리지 않는다 |

D02의 실제 사용자 승인은 확보했다. `tools/check_d02.py`가 로컬 대화의 원래 user message와 보존한 receipt의 hash·repo/ref·허용 동작을 대조한다. 해당 원문이 없는 clone에서는 검사에 실패한다. 이는 암호학적 서명이나 새 권한 발급이 아니며 이후 사용자 변경 지시가 우선한다. D02의 최신 판정은 하네스를 따른다. 승인 범위를 넓히는 merge·배포·공개·별도 engine migration은 별도 대상이다.


## Existing Foundry repository remains unchanged (2026-10-28)

H53 tests pinned main `acbc2d6f368e0de324e39da5f47ce50f974b869d` in independent
copies. Its selected canonical contracts/SDK and complete candidate consumer
match baseline `7547036d1bc9464d6c43a9bdf7cff0a78e8560d7`; five routing sources
are separately tested with the current real API. Existing working checkouts may
be on different revisions; they are not reset or updated. All registered Foundry
worktrees and Git metadata are write protected and compared before/after.

This establishes an adoption rehearsal, not an approved change to an existing
internal project. Organizational adoption, the H50 upstream proposal, new source
publication and independent external acceptance remain separate. The owner has
confirmed no external tester is assigned; only evaluation preparation is authorized.


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
