# sdk

공개 schema와 같은 의미를 보존하는 client·최소 구현을 개발한다.

상태: `python/`에 transport-neutral client·adapter protocol·엄격한 JSON/schema 검사 후보, `typescript/`에 canonical schema를 사용하는 HTTP client 후보를 구현했다. [Python port](../spec/bindings/PYTHON_PORT_0_1.md)와 [HTTP/MCP binding](../spec/bindings/HTTP_MCP_0_1.md)을 따른다.

[Python build](../tools/build_candidate.py)는 schema를 포함한 wheel, [TypeScript build](../tools/build_typescript.py)는 npm tarball을 만든다. H04·H06은 독립 설치와 실제 소비자 실행, H11은 선정 소스만으로 재빌드·재설치를 검증한다. registry에 게시한 package는 아니다. 최신 결과와 환경 범위는 하네스 보고서를 따른다.
