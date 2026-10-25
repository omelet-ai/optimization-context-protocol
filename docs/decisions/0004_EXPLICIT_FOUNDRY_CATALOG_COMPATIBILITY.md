# Foundry catalog를 명시적으로 선택하는 좁은 호환 경로

상태: 2026-10-25 비공개 구현 후보. 현재 통과 여부는 하네스 H15~H18의 증거를 따른다. 이 결정은 OCP adapter의 환경 연결이며 Core·profile·공개 메시지 규격을 변경하지 않는다.

## 근거와 선택

기존 로컬 증거는 식별한 catalog 1.4.0 구현을 사용했다. 내부 소비자 작업의 기록된 main base `e5ec396605221b59d05bb6a6309d95bf734e3771`은 catalog 1.3.0을 제공한다. main 기반 worktree에서 native engine source를 변경하지 않고 실제 API를 기동해 두 catalog를 비교했다. 현재 좌표 profile이 사용하는 `minimize_total_route_cost`, `weight_capacity`, 각각의 evaluation 정의와 solver parameter는 일치한다. 1.4.0의 추가 기능을 OCP의 지원 범위로 확대하지 않는다.

전체 native provider를 먼저 변경하는 대신 adapter에 `catalog_version="1.3.0"` 선택을 추가한다. 기존 호출의 기본값은 1.4.0이다. 선택한 버전·compiler·API·solver와 catalogDigest·전체 문서 SHA-256이 모두 일치해야 한다. 자동 감지, fallback, 버전 범위 허용은 하지 않는다. 따라서 native catalog의 다른 항목만 바뀌어도 다시 검토하고 pin을 갱신해야 한다.

## 호환성과 소비자

`routing.coordinates@0.1.0`의 거리식·반올림·kg·왕복·필수 배정·단위 비용과 실패 의미를 유지한다. basic 거리행렬 입력을 좌표로 변환하지 않는다. 두 catalog의 전체 digest는 다르므로 환경을 바꾸는 운영자는 새 capability pin을 명시적으로 설정한다. 기존 1.4.0 descriptor와 기본 동작은 유지된다. 공개 전 0.1.0 후보는 artifact hash로 식별하며 이번 변경으로 공개 버전이나 인증을 부여하지 않는다.

H15는 명시 선택·버전 불일치·문서 변경·기본값 호환을 검사한다. H16/H17은 선택한 실제 로컬 provider에서 key·한도·네 앱/엔진 조합을 검사한다. H18은 H17과 실제 소비자 범위 승인 D02가 현재 PASS인 뒤에 실행한다. 독립 설치한 private Foundry client와 기존 TMS resolver를 main 기반 엔진에 연결해 실행·평가·재호출을 확인하고 독립 checker로 결과를 검산한다. 기존 1.4.0 경로도 실제 solve로 검사한다. source identity, 기록된 base와의 native source 차이, 소비자 commit과 package hash를 확인한다. 환경·원문·artifact가 없으면 실패한다.

이 증거의 main은 위에 기록한 base이며 최신 원격 main 전체를 의미하지 않는다. H18은 브라우저·외부 사용자·서비스 운영·merge 검사가 아니며 H09/H10의 선행 조건을 대체하지 않는다. 이전 Studio 브라우저 증거의 provider는 1.4.0으로 남는다. 이 좁은 연동을 위해 별도 native provider migration을 필수로 요구하지 않는다. 확장된 native 평가 기능이나 Foundry 전체 기존 실패 수정은 별도 범위다.

## 실행 경계

로컬 비운영·합성 입력·외부 통신 차단을 유지한다. main 1.3.0 검증은 별도 지속 원장에 최대 20회 제출을 기록한다. 기존 1.4.0 원장의 사용량과 상한은 그대로 유지한다. 이는 사용자가 위임한 무과금 로컬 개발의 검증 상한이며 외부 trial 호출·비용 승인이 아니다. 설정·키·실행 원장은 Git과 후보 배포물에 포함하지 않는다.
