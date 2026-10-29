# Fixed-time inspection assignment: owner review exercise

This local candidate is a synthetic first internal project for the owner to
review. Three fictional workers cover six fixed one-hour inspections from 09:00
to 12:00. It uses the same installed `worker.scheduling@0.1.0` profile, native v1
server, SDK, MCP and independent checker as the other examples. Existing Foundry
repositories and services are not changed or required at runtime. This is not
evidence of a deployed internal project or a completed human acceptance test.

## Install and prepare the work

Download and verify the native ZIP from the
[GitHub prerelease](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1),
or build a kit using the repository README's native source quickstart
(`tools/build_native_candidate.py`). Both contain `inspection.py` and this guide.
No internal Foundry checkout or review artifact is needed. From the kit:

<!-- ocp:inspection-init -->
```sh
python3.12 -I -B project.py init --directory '../inspection project'
```

Change into the newly generated `inspection project` directory. If you were given
that project already, skip `init`. Install before editing supplied files:

<!-- ocp:inspection-install -->
```sh
python3.12 -B install.py
```

Python 3.12 is required. No Node, account, API key or LLM call is needed.
Dependencies normally download from public indexes. An offline wheelhouse can
be passed as `--offline-wheelhouse PATH` (repeat for additional folders).
The application is tested on macOS arm64 and offline Linux amd64 emulation.

The supplied UTF-8 CSV files are intentionally small and auditable:

| File | Required columns, in order | Meaning |
| --- | --- | --- |
| `inspection-workers.csv` | `worker_id,start,end,max_minutes` | One available interval and maximum assigned minutes per worker |
| `inspection-tasks.csv` | `task_id,start,end` | Fixed interval; every task must be assigned exactly once |
| `inspection-costs.csv` | `task_id,worker_id,cost` | Each listed pair is eligible; cost is for the whole assignment |

Times are same-day `HH:MM` from local midnight, converted to integer minutes.
`24:00` is accepted only as an end. There is no timezone, DST, date, overnight
or travel-time conversion. Intervals are half-open: 09:00–10:00 and 10:00–11:00
can be assigned to the same worker. Cost is an integer `cost_unit`, **not an
hourly rate or currency**. Missing pairs mean ineligible, never zero cost. A task
with no eligible pairs remains in the problem; the solver can prove it infeasible.

This CSV application accepts ASCII IDs beginning with a letter followed by letters,
digits, `_` or `-` (64 characters maximum), one available interval, at most 4
workers and 8 tasks. Empty/unknown/duplicate columns, duplicate IDs or pairs,
unknown references, invalid times, fractional costs and extra rows are errors.
Errors identify file, row and field. No ignored columns, silent rounding or trimming.
The CSV application's day/identifier restrictions are not new Core requirements.
Native JSON supports the broader profile, including multiple availability intervals.

<!-- ocp:inspection-baseline -->
```sh
.native/bin/python -I -B inspection.py prepare --workers inspection-workers.csv --tasks inspection-tasks.csv --costs inspection-costs.csv --output scenarios/baseline
.native/bin/python -I -B project.py run --project scenarios/baseline/project.json --output runs/inspection-baseline
.native/bin/python -I -B inspection.py report --run runs/inspection-baseline --output reviews/baseline
```

Open `reviews/baseline/REVIEW.md`, `assignments.csv` and `worker-loads.csv`.
The expected optimum is **16 cost units**:

| Worker | Tasks | Assigned minutes | Maximum minutes |
| --- | --- | --- | --- |
| alex | pump, valve | 120 | 120 |
| blair | safety, report | 120 | 180 |
| casey | panel, meter | 120 | 120 |

Report generation rechecks the saved request and solution using the independent
checker, without starting the solver. It does not trust a stored PASS. Import,
run and report directories are new-only; use new names for another experiment.
`IMPORT.json` preserves CSV hashes and meaning; `run.json` preserves job identity.
These hashes detect changed bytes, not forged internally consistent transcripts.

## Change a workload constraint

Alex can spend only 60 minutes on inspections. Preserve the original CSV and
change only the workload budget in a copy:

<!-- ocp:inspection-change -->
```sh
.native/bin/python -I -B - <<'PY'
import csv
from pathlib import Path
with Path('inspection-workers.csv').open(newline='') as f:
    rows = list(csv.DictReader(f))
for row in rows:
    if row['worker_id'] == 'alex': row['max_minutes'] = '60'
with Path('inspection-short-workers.csv').open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['worker_id','start','end','max_minutes'])
    writer.writeheader(); writer.writerows(rows)
PY
.native/bin/python -I -B inspection.py prepare --workers inspection-short-workers.csv --tasks inspection-tasks.csv --costs inspection-costs.csv --output scenarios/short
.native/bin/python -I -B project.py run --project scenarios/short/project.json --output runs/inspection-short
.native/bin/python -I -B inspection.py report --run runs/inspection-short --output reviews/short
.native/bin/python -I -B project.py compare runs/inspection-baseline runs/inspection-short
```

Expect optimum **19**, a difference of **+3**, and `same_problem: false`.
Alex now covers valve, Blair covers pump/safety/report, Casey covers panel/meter.
This measures the changed workload condition, not an engine-quality ranking.
Changing `end` instead changes availability; workload and availability are different.

## Swap the engine and use MCP

<!-- ocp:inspection-byo -->
```sh
.native/bin/python -I -B -m pip install --no-index --no-deps ./ocp_worker_greedy_example-0.1.0-py3-none-any.whl
.native/bin/python -I -B project.py run --project scenarios/baseline/project.json --engine byo --output runs/inspection-byo
.native/bin/python -I -B inspection.py report --run runs/inspection-byo --output reviews/byo
.native/bin/python -I -B project.py compare runs/inspection-baseline runs/inspection-byo
```

The reference and independently implemented greedy engine use the same app and
input. The greedy engine can report `feasible` or `unknown`; it never claims an
optimum or impossibility. `unknown` does not mean the problem is infeasible.
If there is no solution, cost and worker loads stay null and no assignment/load
CSV is emitted. A checker PASS on `unknown` is not an accepted assignment.

<!-- ocp:inspection-mcp -->
```sh
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --input scenarios/baseline/input.json
```

This runs real local stdio MCP context → requirements → validate → submit → job →
result → evaluate and a same-key replay, followed by independent checking. It
calls no model. The input is exactly the one produced by the CSV importer.

## Owner acceptance checklist

Automation covers installation, CSV conversion, real execution, changed workload
and availability, missing eligibility, engine exchange, MCP, and corrupted-result
rejection. Separate expected values and checks verify the data conversion itself.
Do not infer business adoption from the automated result.

`scenarios/baseline/OWNER_REVIEW.json` starts at `NOT_RUN`; fill it only after
actually reviewing the exercise. Record the reviewer, exact run manifest hash,
PASS/FAIL for each criterion, and any issue. No personal or customer data is needed.

| Criterion | Owner action and acceptance condition |
| --- | --- |
| Business scope | Confirm fixed tasks, one worker per task and listed eligibility represent the intended pilot |
| Data meaning | Explain one row of each CSV, whole-task cost, time origin and missing-pair meaning without assistance |
| Assignment usability | Read all six assignments and check worker loads against availability and budgets |
| Change explanation | Make an additional CSV change, run in a new folder, and explain the cost/status change |
| Unsupported rules | Identify whether travel, mandatory breaks, fairness, labor rules or uncertainty are required; if so mark current fit FAIL and record the missing rule |

Verification is explicitly separated: feasibility and cost are recalculated;
optimality/infeasibility use bounded enumeration only within the 8-task/4-worker
profile; engine execution attestation is NOT_CHECKED. Business fit and human
acceptance remain NOT_RUN until reviewed. A synthetic review cannot establish
production reliability, departmental deployment or independent external adoption.

## 내부 검토자를 위한 안내

이 사례는 사용자님이 선택한 **고정 시간 점검 작업 배정**의 합성 도입 후보입니다.
CSV 세 장을 업무 입력으로 삼고 같은 native 서버·SDK·MCP·검산기를 재사용합니다.
기존 Foundry 저장소와 제품 설정은 수정하지 않습니다. 기준 비용 16과 작업량 축소 후
19가 나오는 이유를 배정표에서 확인하고, 직접 조건 하나를 더 바꿔 검토해 주세요.
`OWNER_REVIEW.json`의 수락 여부는 실제 검토 후에만 작성합니다. 이동·휴식·공정성 등
필수 업무 규칙이 빠져 있으면 현재 범위의 업무 적합성은 실패로 기록해야 합니다.
자동 검증 통과는 내부 조직의 실제 도입 완료가 아닙니다.
