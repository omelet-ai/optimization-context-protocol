# Optimization Context Protocol (OCP)

A common interface connecting optimization engines with apps and AI agents.

OCP는 목적·제약·데이터 요구·실행·결과·평가를 공통 의미로 교환하는 최적화 인터페이스를 개발한다. 외부 개발자가 자기 앱과 자기 엔진으로 독립 활용할 수 있게 Core, domain/execution/environment profile과 binding을 구분한다.

현재 저장소는 **비공개 개발 후보**다. 인터넷 공개, 라이선스·특허 검토, 실제 Omelet trial과 외부 사용자 검증은 완료되지 않았다. `0.1.0`은 아직 동결하지 않은 candidate 버전이다.

## 시작하기

- **Run locally:** 계정 없이 실제 OR-Tools와 [Python App A](examples/app-a/README.md)를 실행한다.
- **Bring your engine:** OR-Tools 없이 실행하는 [자기 library 예제](authoring/README.md)와 독립 적합성 검사기를 사용한다.
- **Try Omelet:** 제한된 실제 Omelet 엔진을 권장 체험 경로로 준비한다. 현재 로컬 정책 검사를 실제 서비스 성공으로 표시하지 않는다.

[사용 안내](docs/users/GETTING_STARTED.md), [호환 범위](docs/users/COMPATIBILITY.md), [기여·지원](docs/users/CONTRIBUTING_SUPPORT.md)을 참고한다. Python/TypeScript package는 로컬 build 후보이며 공개 registry에서 설치할 수 있다고 가정하지 않는다.

## 구현과 검증

| 영역 | 구현 범위 |
| --- | --- |
| `spec/` | Core·routing·sync·선택 HTTP/MCP·환경 정책 후보와 schema |
| `sdk/`, `adapters/`, `runtime/` | Python/TypeScript client, 실제 OR-Tools, loopback HTTP·MCP, 로컬 trial 정책 |
| `conformance/`, `cases/` | 독립 평가·transcript 검사·합성 사례·작은 oracle |
| `authoring/`, `examples/` | BYO library, Python App A, TypeScript App B |
| `tools/`, `harness/` | 독립 build·설치·회귀 검사와 단계별 증거 관리 |

진행 상태는 [TASKS](TASKS.md), 단계와 실행은 [하네스 안내](harness/README.md), 새 환경 준비는 [개발 안내](docs/development/LOCAL_RUNTIME.md)를 따른다. 실제 OR-Tools 실행, 공식 MCP SDK host, 격리 설치와 BYO 검사는 구현되어 있다. 실제 Omelet trial·두 앱×두 엔진·실제 외부 개발자 과제·공개 출시는 별도 관문이다.

## 저장소 범위

이 저장소는 [명시적 추적 목록](provenance/repository-selection.json)의 파일만 포함한다. 내부 사업·특허·환경 자료, 원본 snapshot, 이관 원경로 목록, 인증정보, dependency cache와 생성된 실행 보고서는 업로드하지 않는다. 로컬 원본은 보존한다.

```sh
python3 -B tools/verify_repository.py
python3 -B tools/verify_repository.py --index
```

첫 명령은 선정 소스와 문서 링크를, 두 번째는 실제 Git index의 파일 목록·내용을 검사한다. 공개 권리의 판정은 별도 [publication 정책](provenance/publication.json)과 [체크리스트](PUBLIC_RELEASE_CHECKLIST.md)를 따른다. 비공개 저장소 생성·push 승인이 인터넷 공개나 서비스 배포를 허용하지 않는다.
