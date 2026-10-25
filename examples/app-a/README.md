# App A: no-key Python consumer

비공개 기술 후보다. Python 3.12 / macOS arm64에서 독립 설치를 검사한다. 공개 registry 게시는 아직 없다.

개발 환경에서 `python -B tools/build_candidate.py`로 wheel을 만든 뒤 별도 환경에 `ocp_candidate-0.1.0-py3-none-any.whl[reference]`를 설치한다. App A에는 이 파일과 자기 `routing.basic` 입력 JSON만 필요하다. 예제 입력은 `cases/routing/basic-matrix.json`의 `input` 객체다.

```sh
python -B main.py --input my-routing-input.json --time-limit-ms 1000
```

`--configuration`으로 선택 JSON을 명시할 수 있다. 지원하지 않는 목적·weight·제약 조합은 오류다. 출력은 Core result/failure JSON이며 failure는 종료 코드 2다. `unknown`은 실행 응답이고 infeasible 증명이 아니다. 실제 OR-Tools Routing library를 사용하며 계정·API key·원격 서버를 요구하지 않는다.

직접 제공한 정수 meter 거리 행렬과 kg demand/capacity를 사용한다. 주소 geocoding·시간창·멀티트립은 지원하지 않는다. 최적성은 주장하지 않는다. 단일 차량 capacity를 포함한 구현 범위는 H04에서 실제 실행으로 검사한다. Omelet engine과의 교환성은 H09 전까지 미검증이다.
