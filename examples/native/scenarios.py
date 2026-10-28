"""Create small synthetic business inputs without importing any solver or SDK."""
import argparse
from copy import deepcopy
import json
from pathlib import Path


def scenarios():
    routing = {'depot': 'warehouse', 'load_unit': 'kg',
        'visits': [{'id': name, 'demand': 2} for name in ['north', 'market', 'station']],
        'vehicles': [{'id': 'van', 'capacity': 6}],
        'matrix': {'unit': 'meter', 'model': 'explicit_matrix', 'rounding': 'none',
                            'node_ids': ['warehouse', 'north', 'market', 'station'],
                            'values': [[0, 1, 3, 6], [1, 0, 2, 5], [3, 2, 0, 3], [6, 5, 3, 0]]}}
    worker = {'time_unit': 'minute', 'cost_unit': 'cost_unit',
        'workers': [{'id': name, 'availability': [{'start': 0, 'end': 180}], 'max_minutes': 180}
                    for name in ['ava', 'ben', 'cy']],
        'tasks': [{'id': name, 'start': start, 'end': end, 'eligible_workers': ['ava', 'ben', 'cy'],
                   'costs': dict(zip(['ava', 'ben', 'cy'], costs))}
                  for name, start, end, costs in [('receive', 0, 60, [1, 4, 5]), ('pack', 60, 120, [1, 4, 5]),
                      ('dispatch', 120, 180, [1, 4, 5]), ('audit', 30, 90, [2, 3, 4])]]}
    inventory = {'quantity_unit': 'item', 'period_unit': 'day', 'cost_unit': 'cost_unit', 'periods': 3,
        'products': [{'id': 'filter', 'demand': [1, 2, 1], 'scheduled_receipts': [0, 0, 0],
                     'initial_inventory': 1, 'lead_time': 1, 'max_order_quantity': 4, 'storage_capacity': 5,
                     'terminal_min_inventory': 0, 'unit_order_cost': 2, 'fixed_order_cost': 3, 'holding_cost': 1}]}
    base = {'routing-basic': routing, 'worker-scheduling': worker, 'inventory-replenishment': inventory}
    result = {}
    for domain, data in base.items():
        result[domain] = {label: deepcopy(data) for label in ['base', 'changed', 'infeasible', 'invalid']}
    r = result['routing-basic']
    r['changed']['matrix']['values'] = [[0, 1, 3, 10], [1, 0, 2, 9], [3, 2, 0, 7], [10, 9, 7, 0]]
    r['infeasible']['visits'][0]['demand'] = 7
    r['invalid']['matrix']['unit'] = 'km'
    w = result['worker-scheduling']
    w['changed']['workers'][0]['max_minutes'] = 120
    for t in w['infeasible']['tasks']: t.update(eligible_workers=['ava'], costs={'ava': 1})
    w['invalid']['time_unit'] = 'hour'
    i = result['inventory-replenishment']
    i['changed']['products'][0]['demand'] = [1, 2, 2]
    i['infeasible']['products'][0]['demand'] = [2, 2, 1]
    i['invalid']['quantity_unit'] = 'kg'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('my-inputs'))
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    for domain, variants in scenarios().items():
        for label, data in variants.items():
            (args.output / f'{domain}-{label}.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'files': 12, 'synthetic': True}))


if __name__ == '__main__': main()
