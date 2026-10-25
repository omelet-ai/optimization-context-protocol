# 독립 개발·검증 환경

검증한 조합은 CPython 3.12.15, macOS arm64, Node 24.22.0이다. Python dependency는 [lock](../../tools/requirements-dev.lock), 공개 wheel의 SHA-256은 [manifest](../../tools/dependency-wheels.json)에 고정한다. 다른 OS·arch는 실제 검증과 별도 wheel manifest가 필요하다.

프로젝트 루트에서 workspace 밖의 가상환경을 사용한다. 초기 준비에는 공개 package 다운로드가 필요하며, 설치 이후 제품 검사는 오프라인 cache와 loopback/stdio를 사용한다. 회사 계정·서비스 key는 필요하지 않다.

```sh
python3.12 -m venv /tmp/ocp-dev
/tmp/ocp-dev/bin/python -m pip install -r tools/requirements-dev.lock
/tmp/ocp-dev/bin/python -m pip download --only-binary=:all: --no-cache-dir --dest .harness/work/wheels -r tools/requirements-dev.lock
```

TypeScript는 `sdk/typescript/package-lock.json`을 사용한다. Node와 같은 디렉터리에 npm이 있어야 한다. 기본 Node 위치는 `~/.local/bin/node`이며 직접 검사에서는 `OCP_NODE`로 지정할 수 있다. compiler dependency는 source tree 밖에서 먼저 준비한다.

```sh
mkdir -p /tmp/ocp-ts-deps
cp sdk/typescript/package.json sdk/typescript/package-lock.json /tmp/ocp-ts-deps/
npm ci --prefix /tmp/ocp-ts-deps --ignore-scripts --no-audit --no-fund --cache /private/tmp/ocp-npm-cache
```

## Clone에서 실행하는 독립 검사

```sh
/tmp/ocp-dev/bin/python -B tools/verify_repository.py
/tmp/ocp-dev/bin/python -B tools/tests/test_harness.py
/tmp/ocp-dev/bin/python -B tools/check_h01.py
/tmp/ocp-dev/bin/python -B tools/check_h02.py
/tmp/ocp-dev/bin/python -B tools/check_h03.py
/tmp/ocp-dev/bin/python -B tools/check_h04.py
/tmp/ocp-dev/bin/python -B tools/check_h05.py
/tmp/ocp-dev/bin/python -B tools/check_h06.py
/tmp/ocp-dev/bin/python -B tools/check_h07.py
/tmp/ocp-dev/bin/python -B tools/check_h11.py
```

H04·H06·H07·H11은 system-site-packages 없는 임시 Python 환경에 hash를 확인한 wheel만 설치한다. H06/H07은 실제 127.0.0.1 HTTP와 stdio 통신을 사용하므로 해당 로컬 실행 권한이 필요하다. 공개 서버 배포 검사가 아니다. MCP host는 공식 Python SDK Client이며 Claude Code/Desktop의 실제 trial 연결은 미검증이다.

H11은 명시적으로 선정한 소스만으로 Python SDK·독립 checker wheel과 TypeScript tarball을 빌드한다. 새 환경에서 OR-Tools 없이 실제 BYO library와 checker를 실행하고 추출 소스의 재빌드·재설치를 확인한다. 통과한 파일은 `.harness/work/review-candidate/`에 보관한다. 이 생성물은 Git에 넣지 않는다.

## 원본 보유 개발 공간의 단계별 하네스

```sh
python3 -B tools/harness.py validate
python3 -B tools/harness.py status
python3 -B tools/harness.py next
python3 -B tools/harness.py run H00
```

run/status는 동일한 Python 3.12 환경을 사용한다. H00의 `verify_workspace.py`는 로컬 원본 snapshot·내부 이관 목록·legacy 반례까지 엄격하게 검사한다. 원본이 없는 Git clone에서 이 검사를 PASS로 바꾸지 않는다. 위 독립 검사의 성공은 H00 원본 이관 검증이나 H08 실제 trial, 공개·외부 사용자 승인으로 승격하지 않는다. 하네스 보고서는 `.harness/runs/`에 보존하고 원격 추적에서 제외한다.
