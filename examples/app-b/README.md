# App B: TypeScript HTTP consumer

Node 24의 CLI 소비자다. 꾸러미 또는 후보 tarball, package.json, tsconfig.json, main.ts를 같은 새 폴더에 두고 실행한다.

```sh
npm install --no-save --package-lock=false --ignore-scripts --no-audit --no-fund ./ocp-candidate-0.1.0.tgz
npm run build
node dist/main.js http://127.0.0.1:8765 my-routing-input.json --request-id my-job-1
```

HTTP provider는 별도 터미널에서 reference extra를 설치한 Python으로 `python -B -m ocp_runtime.http_server --port 8765`를 실행한다. 입력 생성, 자기 앱 평가, 초대 engine과 오류 복구는 [전체 시작 안내](../../docs/users/DEVELOPER_QUICKSTART.md)를 따른다.

다른 입력/작업에는 새 --request-id를 선택하고 동일 요청 재시도에는 기존 ID를 유지한다. 자동 ID 변경·재시도를 하지 않는다. 실패 종료 코드는 2다. 초대 provider의 key는 OCP_TRIAL_TOKEN 환경변수로 전달하며 로그·명령 기록에 값을 넣지 않는다. Client.evaluate(request, solution)는 solve 없이 평가하며 결과의 정체성과 버전을 대조한다. Node SDK이며 브라우저 직접 호출·async job은 제공하지 않는다. registry 게시·실제 외부 사람의 수락은 별도다.
