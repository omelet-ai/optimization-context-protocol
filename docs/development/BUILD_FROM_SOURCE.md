# First build from selected source

프로젝트 또는 선정 source bundle의 루트에서 실행한다. Python 3.12와 Node 24/npm을 PATH에 준비한다. 의존성 설치는 공개 PyPI/npm에 접속하며 회사 계정·trial key는 필요 없다. 첫 빌드의 온라인 준비와 이후 오프라인 검사를 구분한다.

```sh
python3.12 -m venv /tmp/ocp-build
/tmp/ocp-build/bin/python -m pip install --no-compile build==1.4.0 setuptools==80.9.0 wheel==0.46.3
/tmp/ocp-build/bin/python -B tools/build_candidate.py
/tmp/ocp-build/bin/python -B tools/build_conformance.py
node --version
npm --version
export OCP_NPM_CACHE=/tmp/ocp-build-npm-cache
/tmp/ocp-build/bin/python -B tools/build_typescript.py
```

결과 경로는 각 명령의 JSON에 나온다. 기본은 `.harness/work/dist/`다. Node/npm은 PATH에서 찾으며 특수 설치에서는 `OCP_NODE`와 `OCP_NPM`에 각 실행 파일의 절대 경로를 지정할 수 있다. 기존 개발자 홈 경로나 다른 머신의 cache가 필요하지 않다. npm cache는 OCP_NPM_CACHE 또는 npm 기본 설정을 따른다.

온라인 준비 후 같은 cache로 재현하려면 다음 명령을 쓴다. cache가 없으면 실패하며 온라인으로 자동 전환하지 않는다.

```sh
/tmp/ocp-build/bin/python -B tools/build_typescript.py --offline
```

원본 저장소에서 추가로 `tools/build_invitation_kit.py --output /tmp/ocp-new-kit`를 실행하면 문서·샘플·wheel·tarball·독립 checker를 새 꾸러미로 묶는다. 기존 출력 폴더는 덮어쓰지 않는다. 선정 source bundle에는 exporter 자체가 없으므로 위 개별 builder를 사용한다. 새 파일명·hash를 보존하고 같은 candidate 버전이라도 이전 artifact와 혼용하지 않는다. 설치·앱·엔진 연결은 [개발자 시작 안내](../users/DEVELOPER_QUICKSTART.md)를 따른다.
