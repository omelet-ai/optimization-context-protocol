"""Write small engine-swap counterexamples, without running either engine."""
import argparse
from copy import deepcopy
import json
from pathlib import Path


def scenarios():
    workers = [{'id': wid, 'availability': [{'start': 0, 'end': 180}], 'max_minutes': 180} for wid in ['a', 'b']]
    tasks = [{'id': tid, 'start': 0, 'end': 60, 'eligible_workers': ['a', 'b'], 'costs': {'a': 1, 'b': 2}}
             for tid in ['t01', 't02']]
    gap = {'time_unit': 'minute', 'cost_unit': 'cost_unit', 'workers': workers, 'tasks': tasks}
    gap['tasks'][1]['costs']['b'] = 100
    trap = deepcopy(gap)
    trap['tasks'][1].update(eligible_workers=['a'], costs={'a': 1})
    impossible = deepcopy(trap)
    impossible['tasks'][0].update(eligible_workers=['a'], costs={'a': 1})
    adjacent = deepcopy(gap)
    adjacent['tasks'][1].update(start=60, end=120)
    changed = deepcopy(adjacent)
    changed['workers'][0]['max_minutes'] = 60
    invalid = deepcopy(adjacent)
    invalid['time_unit'] = 'hour'
    return {'adjacent': adjacent, 'changed-budget': changed, 'quality-gap': gap, 'greedy-trap': trap,
            'infeasible': impossible, 'invalid-unit': invalid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('byo-inputs'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    for name, value in scenarios().items():
        (args.out / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'status': 'PREPARED', 'inputs': len(scenarios()), 'execute_calls': 0, 'model_calls': 0}))


if __name__ == '__main__':
    main()
