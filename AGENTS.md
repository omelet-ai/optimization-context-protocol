# OCP Open Source 작업 규칙

## 목표와 경계

- 범용성·확산성을 우선한다. 외부 개발자가 자기 앱과 자기 엔진으로 독립 활용할 수 있어야 한다.
- 규격·적합성은 중립적으로 유지하고 Omelet 제한 trial을 권장 첫 체험으로 제공한다. no-key·BYO 경로도 유지한다.
- Core, domain/execution/environment profile, binding, 제품 정책을 구분한다. 특정 endpoint·OIP·AppKit·앱 구조를 공통 필수로 만들지 않는다.
- 기존 Foundry 구현은 근거 자료다. 더 나은 규격을 위해 새로 설계할 수 있고 내부 consumer도 별도 migration으로 바뀔 수 있다.

## 소유 경로

- `spec/`: 새 규범·schema·호환 정책. 제안과 승인된 규범 상태를 명시한다.
- `sdk/`, `adapters/`, `runtime/`: 독립 공개 구현. 참조 snapshot이나 다른 checkout을 runtime에서 import하지 않는다.
- `authoring/`, `conformance/`, `examples/`, `cases/`: 독립 저작·검증·사용 사례.
- `reference/imported-foundry/`: 해시 검증한 원본 snapshot. 수정하지 않고 필요한 부분은 새 개발 영역에 출처와 함께 옮긴다.
- `.private/`: 내부 원본·특허·사업·제품 참고 자료. 공개 대상에 넣지 않는다.
- `provenance/`: 파일 출처·미커밋 상태·권리·공개 allowlist.

## 의미와 구현

- 선언과 실행을 일치시킨다. 지원하지 않는 목적·제약·가중치·조합을 추측하거나 무시하지 않는다.
- optimized/reported, enforced/evaluated, feasible/optimal/infeasible/unknown을 구분한다.
- timeout·휴리스틱 미발견을 infeasible로, 미평가 null을 0으로 바꾸지 않는다. mock 성공·가짜 async를 만들지 않는다.
- 같은 profile 교집합에서만 엔진 교환성을 주장하고 단위·거리식·반올림·비용계수를 확인한다.
- trial은 실제 엔진을 사용한다. 외부 trial key는 내부 서비스 토큰과 분리하고 신원·기능·한도·만료·회수를 서버에서 집행한다.

## 개발과 검증

- [작업 원장](TASKS.md), [하네스 안내](harness/README.md), `harness/plan.json`을 따른다. 로컬 원본 보유 공간에서는 `docs/plans/OCP_OPEN_SOURCE_RELEASE_PLAN.md`와 `docs/plans/OCP_AUTONOMOUS_HARNESS_PLAN.md`도 따른다. 이 내부 계획은 원격 저장소에서 제외한다. 역할 실명·특허 상태·실행 성과를 추정해 채우지 않는다.
- 재개 시 `python3 -B tools/harness.py status`와 `next`로 현재 증거와 다음 작업을 확인한다. 원본 snapshot이 없는 clone에서는 H00 이관 검증을 통과한 것으로 만들지 않고 [독립 검사 안내](docs/development/LOCAL_RUNTIME.md)를 따른다.
- 사용자가 위임한 로컬 개발·검증은 에이전트가 설계→구현→검사→수정→증거 기록까지 수행한다. 단계별 테스트 실행이나 일상적인 구현 선택을 사용자에게 반복해서 넘기지 않는다.
- 선행 게이트의 현재 PASS 없이 의존 단계로 진급하지 않는다. 코드·검사·선행 증거 변경으로 만료된 결과, 미구현·skip·외부 미접속을 PASS로 바꾸지 않는다. 독립적으로 준비된 작업은 계속할 수 있다.
- 비공개 기술 후보의 PASS와 P0 권리·실제 담당·예산·외부 환경·사용자 시험·게시 승인을 구분한다. 실제 외부 결정은 준비물을 갖춘 뒤 필요한 범위만 요청하며 승인 사실을 만들어 기록하지 않는다.
- 변경된 모듈을 검사하고 public contract 변경은 versioning·consumer 검증을 포함한다. 증거에 실행 범위를 적는다.
- `python3 tools/verify_workspace.py`로 이관 무결성과 사례를 확인한다. 이 검사를 제품 전체 PASS로 표현하지 않는다.
- 새 구현이 독립 설치·build·test·실행을 통과한 뒤에만 실행 가능한 package라고 안내한다.

## 파일과 공개

- 원본을 삭제하지 않는다. source snapshot에 `.env*`, 인증정보, 운영 데이터, 비공개 solver 구현·배포 설정을 추가하지 않는다.
- `.gitignore`만으로 공개 안전을 판단하지 않는다. `provenance/publication.json`의 명시적 allowlist와 P0 권리·라이선스·특허 검토가 필요하다.
- LICENSE를 임의로 적용하거나 기존 package의 MIT 표기를 전체 공개 권한으로 해석하지 않는다.
- 원격 저장소·branch·commit/push·PR·release·workflow·registry 게시·배포는 정확한 대상과 동작에 대한 사용자 승인을 별도로 확인한다.
- 사용자는 2026-10-25에 `omelet-ai/optimization-context-protocol` 비공개 저장소 생성과 내부 자료·원본 snapshot을 제외한 첫 commit/push를 승인했다. [추적 목록](provenance/repository-selection.json)과 `tools/verify_repository.py --index`로 실제 포함 파일을 검사한다. 이 승인은 인터넷 공개·라이선스 확정·서비스 배포 승인이 아니다.
- 사용자는 같은 날 H04의 일회성 실패 조사와 필요한 수정 검증 후, 내부 자료·키·실행 증거를 제외한 후속 코드·문서를 같은 비공개 저장소에 commit/push하도록 승인했다. 외부 trial 담당자·환경·예산은 별도 결정으로 남는다.
- 사용자는 2026-10-26에 담당을 직접 맡고 합리적인 의사결정과 빠른 외부 시험 준비를 위임했다. 기존 외부 환경은 없으며 단기 시험 배포안 준비를 선택했다. 담당 배정을 다시 요청하지 않는다. 권리 검토 결과·정확한 외부 배포 대상·비용 지출의 승인은 별도로 구분한다.
