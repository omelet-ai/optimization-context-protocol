# Minimal internal consumer candidate

상태 확인: 2026-10-25. [Foundry draft PR #428](https://github.com/omelet-ai/oi-foundry/pull/428), `feat/ocp-consumer-integration`, head `4528ccac2b383e10e4dd3315bd2b31540d7fc272`, 검증 base `e5ec396605221b59d05bb6a6309d95bf734e3771`.

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
| merge와 제품 반영 | draft 상태다. 소유자 검토·판정 기준 승인·merge·배포는 완료되지 않았다 |
| OCP H10 | H09와 D02가 선행한다. 최소 연동의 구현·승인 사실과 H10의 전체 PASS를 구분한다. H09 외부 trial이 완료되기 전에 H10을 올리지 않는다 |

D02의 실제 사용자 승인은 확보했다. `tools/check_d02.py`가 로컬 대화의 원래 user message와 보존한 receipt의 hash·repo/ref·허용 동작을 대조한다. 해당 원문이 없는 clone에서는 검사에 실패한다. 이는 암호학적 서명이나 새 권한 발급이 아니며 이후 사용자 변경 지시가 우선한다. D02의 최신 판정은 하네스를 따른다. 승인 범위를 넓히는 merge·배포·공개·별도 engine migration은 별도 대상이다.
