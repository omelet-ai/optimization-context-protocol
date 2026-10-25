# App B: TypeScript HTTP consumer

Node 24의 CLI 앱으로, 독립 설치한 TypeScript SDK와 자기 입력을 사용한다. UI나 Foundry가 필요하지 않다. 실제 엔진은 별도 HTTP provider가 선택한다.

```sh
python -B -m ocp_runtime.http_server --port 8765
node dist/main.js http://127.0.0.1:8765 my-routing-input.json
```

서버는 후보 Python wheel의 `[reference]`, 앱은 `tools/build_typescript.py`가 만든 비공개 npm tarball을 설치한 환경에서 실행한다. `main.ts`를 TypeScript 7.0.2로 컴파일한다. 테스트는 이를 새 임시 폴더에서 수행한다. npm registry 게시나 production HTTP 환경을 제공한 것은 아니다.

서버 endpoint 선택만으로 연결하며 계약의 configuration/profile을 임의 변환하지 않는다. 실패와 null을 보존한다. 호출이 끊기면 자동 재시도하지 않는다. [좌표 profile](../../spec/profiles/ROUTING_COORDINATES_0_1.md) provider끼리는 같은 입력을 사용할 수 있다. 승인된 로컬 Omelet trial endpoint에는 `OCP_TRIAL_TOKEN` 환경변수로 별도 key를 전달한다. SDK가 request_id에서 멱등키를 계산하며 같은 요청의 명시적 재호출은 서버에 보존된 응답을 재사용한다. H17은 설치 앱과 두 실제 엔진의 로컬 교집합을 검사한다. H08/H09의 외부 운영 및 실제 사용자 검증은 별도다.
