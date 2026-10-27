# Contribution, rights and support candidate

공개된 OCP 원본 소스에는 [Apache-2.0](../../LICENSE)을 적용한다. 회사의 공개·배포 권리와 특허 관점 공개 가능 여부는 담당자가 확인했다. 특허 출원·등록 상태나 회사 전체 특허 허가를 의미하지 않는다. 제3자 의존성은 자체 라이선스를 유지한다. 지원 SLA와 응답 시간은 미확정이다.

기여 제안에는 문제/지원 범위, 재현 입력, 예상 의미, Core/profile 버전, 실제 검사 범위와 실패 결과를 포함한다. 합성 입력을 쓰며 key·개인정보·운영 데이터를 첨부하지 않는다. 오류 보고는 solver 미발견/timeout과 증명된 infeasible을 구분하고 미평가 값을 0으로 채우지 않는다.

module 검사→독립 conformance→consumer→설치 artifact 순서로 영향 검증한다. 원본 snapshot·다른 checkout import 없이 build되어야 한다. 공개 계약 변경에는 migration과 호환 사례가 필요하다. Unsupported 기능은 명확히 거절하며 정상 응답처럼 위장하지 않는다.

비민감 버그와 연동 제안은 GitHub 이슈를 이용한다. 보안 문제는 저장소의 비공개 취약점 보고 또는 기존 초대 담당자의 비공개 채널로 전달한다. 실 token이 포함된 공개 issue를 만들지 않는다. 현재 로컬 실험은 외부 지원을 제공하는 운영 서비스가 아니다. 실제 외부 개발자 시험과 지원 시간은 별도로 기록한다.
