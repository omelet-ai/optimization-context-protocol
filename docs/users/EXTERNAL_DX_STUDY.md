# External developer study kit — candidate

이 과제지는 H12 실행 준비물이다. 참여자 모집·연락·자료 제공·trial 키 발급은 아직 수행하지 않았다. 실제 외부 참여 허락, 공유할 artifact의 권리와 대상, trial 환경·운영 담당·예산이 확정된 뒤 사용한다. 에이전트 실행은 외부 사람의 시험 실적으로 계산하지 않는다.

## 진행자가 준비할 것

1. 신규 외부 개발자 5명의 참여 허락과 관찰 동의, 익명 ID `p01`~`p05`를 확보한다. 실명 연결표는 운영 담당이 별도 보관한다.
2. 동일한 candidate artifact SHA-256, Core/profile/binding 및 checker 버전을 고정한다. 버전이 바뀌면 별도 cohort로 분석한다.
3. [시작 안내](GETTING_STARTED.md), [호환 범위](COMPATIBILITY.md), [BYO 시작점](../../authoring/README.md)만 먼저 전달한다. 승인 전 private artifact를 외부에 보내지 않는다.
4. no-key와 trial의 배정·순서를 사전에 적고 각각 결과를 보고한다. 동일인이 두 경로를 사용하면 두 번째는 학습 영향이 있는 재시험으로 구분한다. 서로 다른 경로의 성공률을 합쳐 4/5를 주장하지 않는다.
5. 담당자는 참가자의 요청에 답하되 시점과 개입을 모두 기록한다. 키 발급 대기, 설치 오류와 지원 시간도 전체 시간에 포함한다.

## 참여자 과제

| 과제 | 제공할 지시 | 완료 근거 |
| --- | --- | --- |
| 첫 실행, 목표 15분 | 새 환경에서 안내 문서만 보고 설치하고 샘플 결과와 평가를 확인한다. trial 배정자는 키 발급부터 시작한다 | 실제 engine 식별, request/result, 독립 checker 결과 |
| 자기 입력 | 샘플의 값만 재실행하지 말고 새로운 합성 문제를 작성하고 미지원 입력 하나도 확인한다 | 새 입력과 기대값 설명, 성공/거절 결과, checker |
| 최소 앱 연결, 목표 60분 | Python 또는 TypeScript로 자기 입력을 보내고 결과·실패·미평가 값을 보존하는 작은 앱을 만든다 | 설치 가능한 앱 코드, 실행과 평가, 지원 개입 기록 |
| 자기 엔진 연결 | BYO port를 구현해 실제 자기 계산 코드를 붙이고 정상·거절 사례를 실행한다 | 엔진 구현 및 출처, conformance 보고서, 원본과 차이 |

최소 두 명의 독립 활용을 확인한다. 샘플 복사는 `sample-replay`, 자기 입력·앱·엔진의 독립 작업은 검토 후 `independent-work`로 기록한다. 작업 종류에 따라 과제를 선택할 수 있으며 독립 participant 수는 중복 제거한다. 첫 실행 성공은 독립 구현으로 계산하지 않는다.

## 로컬 계측

진행자는 과제 안내·설치·키 발급 전에 시계를 시작한다. 실패 후 다시 시도할 때 기존 기록을 덮어쓰지 않는다. 이 CLI는 단일 진행자가 기록하는 도구이며 로그 서명·신원 확인 도구가 아니다. 직접 편집한 기록도 담당자의 검토가 필요하다.

```sh
python3 -B tools/dx_study.py start .private/dx-study/p01-first.json \
  --participant p01 --actor external-human --route no-key --task first-run \
  --artifact .harness/work/review-candidate/ocp_candidate-0.1.0-py3-none-any.whl \
  --candidate-version 0.1.0-candidate --suite-version 0.1.0-candidate
python3 -B tools/dx_study.py event .private/dx-study/p01-first.json support-start
python3 -B tools/dx_study.py event .private/dx-study/p01-first.json support-end
python3 -B tools/dx_study.py event .private/dx-study/p01-first.json complete \
  --evidence .private/dx-study/p01-checker-report.json --work sample-replay
python3 -B tools/dx_study.py report .private/dx-study/p01-first.json
```

trial의 `key-requested`·`key-issued`, 중단의 `failed`도 같은 event 명령으로 기록한다. 성공 전에 support/key 대기를 닫는다. 자기 작업은 별도 파일과 `--task own-input`, `integrate-app`, `independent-engine`을 쓴다. 자동 리허설은 반드시 `--actor automated-rehearsal`로 적는다.

기록에는 익명 ID, 시각, 버전, artifact와 증거의 hash만 저장한다. 비밀·실제 고객 입력·이름·token을 넣지 않는다. 실행 결과와 코드의 증거 파일은 `.private/dx-study/` 안에 별도 보관하고 공개 선정 목록에 넣지 않는다. 참여·보존 동의와 삭제 요청은 담당자가 처리한다.

## 판정과 수정 반복

보고서는 각 경로/과제의 첫 시도만 집계한다. 실패·미완료도 분모에 남고, 재시도로 실패를 지우지 않는다. 성공 사례의 중앙값은 실패율과 함께 읽는다. 15분/60분 내 성공과 **지원 없이 성공**을 별도로 표시한다. 참가자마다 첫 배정 경로, 학습 여부와 담당자의 증거 검토를 합쳐 해석한다.

H12의 목표는 신규 5명 중 4명 이상의 문서 기반 첫 실행, 최소 두 명의 독립 활용, 앱 통합 60분 목표의 실측이다. no-key/trial 경로별 표본 크기와 미시험 범위를 함께 표시한다. 이 도구는 숫자가 좋아도 `h12_pass: false`를 유지한다. 실제 신원·동의·독립 수행·증거 검토와 H09/H11/D00 선행 관문은 자동 집계로 증명할 수 없다.

실패는 설치/문서/키 발급/계약/엔진/앱 통합으로 분류하고 해당 모듈을 수정한 뒤 새 artifact에서 재시험한다. 최초 실패 기록과 개입 시간을 보존한다. 담당자가 H12 증거를 검토하기 전 H13 공동 출시 후보로 진급하지 않는다.
