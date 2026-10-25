# 신규 개발 출처와 공개 상태

Core·routing 후보 문서·schema, Python/TypeScript SDK, OR-Tools adapter, HTTP/MCP runtime, 로컬 trial 정책, 독립 conformance, BYO 예제와 개발 하네스는 사용자의 자율 개발 지시에 따라 이 workspace에서 새로 작성했다. 원본 snapshot의 코드를 실행 package로 복사하거나 다른 checkout을 runtime에서 import하지 않는다. 보존한 greedy 반례는 출처가 기록된 합성 사례로 사용하며 원본을 수정하지 않는다.

설계 근거는 [Core 결정](../docs/decisions/0001_MINIMAL_CORE.md)과 [binding 결정](../docs/decisions/0002_BINDING_BOUNDARIES.md)에 연결한다. 외부 표준과 library의 문서는 각 규격·구현 문서에서 표시한다. 설치한 공개 의존성은 [개발 lock](../tools/requirements-dev.lock)으로 버전을 고정한다.

H11의 [candidate-selection](candidate-selection.json)은 비공개 기술 검토용 소스의 명시적 선정 목록이다. 선정된 파일만 별도 디렉터리에서 빌드하며 review-manifest에 각 소스·artifact·dependency lock hash를 기록한다. `.private/`, 원본 snapshot, 내부 계획·환경 파일은 포함하지 않는다. SDK와 checker wheel, TypeScript tarball, 선정 소스 tarball을 검증하고 `.harness/work/review-candidate/`에 보관한다.

새로 작성했다는 사실은 공개 권리·라이선스·특허 검토 완료가 아니다. 이 문서는 로컬 `source-manifest.json`의 snapshot hash를 변경하지 않는다. 파일·dependency별 실제 권리 검토와 공개 결정은 D00/H13에서 준비하고, 공개 allowlist는 [publication](publication.json)을 따른다. 비공개 후보 목록은 공개 allowlist를 대체하지 않는다.
