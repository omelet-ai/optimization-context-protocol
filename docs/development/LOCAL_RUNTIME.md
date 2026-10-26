# 독립 개발·검증 환경

검증한 조합은 CPython 3.12.15, macOS arm64, Node 24.22.0이다. Python dependency는 [lock](../../tools/requirements-dev.lock), 공개 wheel의 SHA-256은 [manifest](../../tools/dependency-wheels.json)에 고정한다. 다른 OS·arch는 실제 검증과 별도 wheel manifest가 필요하다.

프로젝트 루트에서 workspace 밖의 가상환경을 사용한다. 초기 준비에는 공개 package 다운로드가 필요하며, 설치 이후 제품 검사는 오프라인 cache와 loopback/stdio를 사용한다. 회사 계정·서비스 key는 필요하지 않다.

```sh
python3.12 -m venv /tmp/ocp-dev
/tmp/ocp-dev/bin/python -m pip install -r tools/requirements-dev.lock
/tmp/ocp-dev/bin/python -m pip download --only-binary=:all: --no-cache-dir --dest .harness/work/wheels -r tools/requirements-dev.lock
```

TypeScript 첫 온라인 빌드와 Python build prerequisite는 [소스 빌드 안내](BUILD_FROM_SOURCE.md)를 따른다. Node/npm을 PATH에서 찾고, OCP_NODE/OCP_NPM으로 명시 경로를 선택할 수 있다. 하네스는 준비한 cache를 명시해 오프라인으로 실행한다.

```sh
export OCP_NPM_CACHE=/tmp/ocp-npm-cache
/tmp/ocp-dev/bin/python -B tools/build_typescript.py
export OCP_NPM_OFFLINE=1
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
/tmp/ocp-dev/bin/python -B tools/check_dx_study.py
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

다른 Python으로 조회하면 환경 식별이 달라 STALE이 될 수 있다. 실행 명령의 `-B`를 유지해 소스 아래 `__pycache__`가 생성되지 않게 한다. 생성물이 입력 폴더에 들어가면 숨기거나 입력에서 임의 제외하지 말고 workspace 밖으로 옮긴 뒤 실제 소스와 현재 환경을 다시 확인한다. D02는 원래 사용자 승인 메시지의 로컬 출처도 필요하므로 clone의 자동 성공 대상이 아니다.

좌표 계약·reference·upstream 결함 검사는 같은 Python으로 `tools/check_h15.py`를 실행한다. 실제 로컬 엔진 검사는 `tools/check_h16.py`, 설치 앱 네 조합은 `tools/check_h17.py`, 기록된 main 기반 엔진과 Foundry 소비자는 `tools/check_h18.py`다. 실제 엔진 검사는 승인된 로컬 환경 설정이 있어야 하며 없는 clone에서 skip/PASS로 만들지 않는다. 하네스 실행 시 H15→H16→H17→H18과 각 단계의 기존 선행을 따른다. H18은 D02도 요구한다.

H16/H17은 `.private/foundry-verification/settings.json`의 명시적인 버전·문서 pin과 source identity를 사용한다. H18은 승인된 별도 Foundry worktree와 그곳에서 만든 private client package의 정확한 hash도 요구하며, 기존 1.4.0 환경을 별도로 검사한다. 설정의 source·package·예산 값을 추측해서 채우지 않는다. 외부 SDK 사용자가 이 로컬 검증 설정이나 Foundry checkout을 설치할 필요는 없다. 자세한 범위는 [catalog 호환성 결정](../decisions/0004_EXPLICIT_FOUNDRY_CATALOG_COMPATIBILITY.md)을 따른다.

하네스는 OCP_NODE/OCP_NPM/OCP_NPM_CACHE/OCP_NPM_OFFLINE을 검사용 자식 프로세스에 전달하고 증거의 환경 식별에 포함한다. run/status/next에는 동일한 export를 유지한다. 값이 달라지면 이전 증거는 STALE이다. 서비스 token 등 다른 비밀 환경변수는 전달하지 않는다.
