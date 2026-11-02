"""Recompute item detail fields independently; no evidence-builder or engine imports."""
from conformance.assessment import digest
from conformance.core_contract import ContractError
from conformance.evidence_details import detail_report


def verify_details(request, result, objective, preparation, details):
    expected = None
    if result['solution'] is not None:
        chosen = result['solution']['selected']
        rows, cost, value = [], 0, 0
        for item in request['input']['items']:
            if item['id'] in chosen:
                rows.append({'id': item['id'], 'cost': item['cost'], 'benefit': item['benefit']})
                cost += item['cost']
                value += item['benefit']
        if value != objective:
            raise ContractError('EXPLANATION_FACTS_MISMATCH')
        expected = {'items': rows, 'used_capacity': cost,
                    'remaining_capacity': request['input']['capacity']-cost,
                    'total_benefit': value, 'cost_unit': 'credit', 'benefit_unit': 'benefit_unit'}
    if digest(details) != digest(expected):
        raise ContractError('EXPLANATION_FACTS_MISMATCH')
    return detail_report(request, result, details,
                         {'id': 'ocp-budget-detail-checker-example', 'version': '0.1.0'})
