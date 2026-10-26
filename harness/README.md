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
