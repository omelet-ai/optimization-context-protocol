"""Domain definitions only; no solver, checker, SDK or runtime dependency."""
from importlib.resources import files
import json

REFERENCE = {'id': 'example.budget-selection', 'version': '0.1.0'}
SEMANTICS = [
    'Select a subset of at most 12 items once each; total cost must not exceed capacity.',
    'Maximize additive total_benefit; integer credit and benefit_unit are distinct units.',
    'Capacity 0-1000 credit, item cost 0-1000 credit, benefit 0-10000 benefit_unit.',
    'An empty selection is a feasible solution with benefit zero; it is not a null solution.',
    'No precedence, shared multi-resource capacity or uncertainty. No automatic relaxation.',
]


def schema(kind):
    if kind not in ('input', 'solution', 'configuration'):
        raise ValueError('UNKNOWN_SCHEMA')
    return json.loads(files(__package__).joinpath(kind + '.json').read_text())
