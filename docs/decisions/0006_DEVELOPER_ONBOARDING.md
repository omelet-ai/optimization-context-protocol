# Developer onboarding candidate revision

2026-10-26의 자동 외부 엔지니어 리허설에서 중복 JSON, 고정 App B 요청 ID, BYO 실패 종료 코드, 로컬 경로/cache 전제, 설치·진단·MCP 요청 구성·TypeScript 평가·transcript 안내의 문제를 확인했다. H20은 이 아홉 항목과 설치된 소비자 경로를 검증한다. 실제 사람의 H12 수용 기준을 대체하지 않는다.

Core/profile/binding 0.1.0의 wire 의미와 schema는 바꾸지 않는다. 아직 동결하지 않은 candidate package 0.1.0 안에서 TypeScript Client.evaluate와 OCPClientError, MCP의 선택적 ocp://request-guide/0.1.0 resource를 추가했다. 기존 다섯 MCP 도구 이름과 인자는 유지한다. resource는 schema/default/template만 읽으며 solve하지 않는다. 새 API는 후보 artifact hash로 고정하고 Python/TypeScript/MCP 소비자와 실제 local trial을 다시 검사한다.

App B CLI는 --request-id를 필수로 받는다. 이전 `node dist/main.js ENDPOINT INPUT` 호출은 `--request-id JOB_ID`를 추가해야 한다. 동일 작업 재시도는 같은 ID/입력을 유지한다. BYO failure는 종료 코드 2, 초대 CLI·installer의 오류는 구조화된 진단으로 나온다. 자동 ID 변경·quota 초기화·해석 완화는 하지 않는다.

새 꾸러미에는 독립 앱·엔진·transcript 예제와 TypeScript 설정이 포함된다. manifest가 식별하는 파일 집합이 달라졌으므로 이전 installer/manifest와 섞지 않는다. 이전 배포물과 실행 증거는 보존하고 새로운 출력 폴더에서 만든다. 기존 임시 HTTPS 연결의 승인 시간·한도는 연장하지 않으며 새 후보의 로컬 검증은 공개·재배포 승인이 아니다.

POSIX installer는 `python -m venv`처럼 interpreter symlink를 사용한다. PATH의 symlink로 실행한 relocatable Python을 복사하면 표준 라이브러리 위치를 잃을 수 있어, 이 설치 경로도 H20에서 실제 새 환경으로 검사한다.

새 설치의 동시 실행에서 OR-Tools의 최초 native import가 HTTP 10초 제한을 소비하는 문제도 재현했다. reference backend 생성 시 native dependency를 로드해 서버의 준비 완료 안내 전에 초기화를 끝낸다. 초기 준비 검사는 30초까지 기다리며 첫 HTTP 실행의 10초 제한과 solver budget은 유지한다. 실행 재시도나 timeout 성공 변환은 추가하지 않는다. 기본 SDK와 BYO 경로는 reference backend를 만들지 않으면 OR-Tools를 요구하지 않는다.
