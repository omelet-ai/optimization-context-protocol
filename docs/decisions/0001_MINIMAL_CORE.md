# 최소 Core와 검증 경계

상태: 비공개 기술 후보에 적용. 2026-10-24 자율 개발 위임 범위의 설계 결정이며 공개 규범 승인·라이선스 결정과 구분한다.

기존 HTTP jobs·OIP·state·release 구조를 Core에 그대로 넣으면 단일 함수·기존 library·타사 앱도 내부 플랫폼을 구현해야 한다. [Core 후보](../../spec/core/CORE_0_1.md)는 메시지 의미와 versioned profile 참조를 공통화하고 실행·전달·환경은 분리한다.

대안은 기존 Capability Contract 전체 채택, 임의 domain JSON만 전달하는 얇은 envelope, 현재의 명시 configuration·결과·평가 계약이다. 기존 계약 전체 채택은 독립 local 사용 비용이 크고, 얇은 envelope는 미지원 선택·상태·미평가 오류를 검출하기 어렵다. 세 번째 대안을 선택한다.

공통 입력·해 모델, endpoint·tenant·job·서명 키, UI·사람 확인 절차는 Core 필수로 두지 않는다. H01은 schema와 의미 오류를 검사하고 H02부터 실제 domain 규칙을 추가한다. 실제 실행과 권리·외부 사용자 증거는 별도 게이트다.

이전 공개 버전은 없으며 `0.1.0`과 임시 URN은 후보 식별자다. 버전 없는/latest 참조를 거절하고 초기에는 exact match를 사용한다. 내부 계약과의 차이는 adapter·consumer migration으로 해결하며 상세 mapping은 로컬 참고 자료로만 보존한다. 기존 snapshot·운영 API·consumer는 수정하지 않는다.
