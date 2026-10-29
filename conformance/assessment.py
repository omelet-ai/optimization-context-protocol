"""Additive verification-scope report, separate from the Core wire contract.

No solver/provider imports or execution. Existing strict transcript checkers
remain unchanged. Solution-only assessment never verifies a proof claim.
"""
import argparse
from copy import deepcopy
from dataclasses import dataclass
from importlib import import_module
import re
import hashlib
import json
from pathlib import Path

from .core_contract import ContractError, json_values, parse_json, validate_message
from .runner import CHECKERS

REPORT_VERSION = '0.1.0'
SCOPES = {
    'routing.basic': {'solution': 'Profile limit: 64 visits, 16 vehicles; explicit integer meter matrix.',
                      'proof': 'Optimality: enumeration up to 7 visits/3 vehicles. Infeasibility: supported capacity inequalities or bounded enumeration.'},
    'routing.coordinates': {'solution': 'Profile limit: 64 visits, 16 vehicles; independent Haversine conversion and ceil rounding.',
                            'proof': 'Optimality: enumeration up to 7 visits/3 vehicles. Infeasibility: supported capacity inequalities or bounded enumeration.'},
    'worker.scheduling': {'solution': 'Profile limit: 8 fixed-time tasks, 4 workers; coverage, eligibility, availability, no overlap and workload.',
                          'proof': 'Independent Cartesian-product enumeration within profile limits.'},
    'inventory.replenishment': {'solution': 'Profile limit: 4 products, 6 periods and bounded integer stock/orders; deterministic inventory balances and costs.',
                               'proof': 'Independent bounded order-vector enumeration within profile limits.'},
    'assignment.fixture': {'solution': 'Schema-bound feasible assignment witness and cost.', 'proof': 'No optimality or infeasibility checking in this fixture.'},
}



@dataclass(frozen=True)
class ProfileCheck:
    verify: object
    scope: dict
    metric_id: str
    value_key: str
    identity: dict


class CheckerRegistry:
    """Explicit trusted checker selection, keyed by exact profile ID/version.

    Registration is not certification of the supplied Python code. No automatic
    entry-point discovery, network fetch, or import from a problem/result field.
    """
    def __init__(self):
        self._checks = {}

    def register(self, reference, verify, *, scope, metric_id, value_key, identity):
        for ref in [reference, identity]:
            if not isinstance(ref, dict) or set(ref) != {'id', 'version'} or any(not isinstance(v, str) or not v for v in ref.values()):
                raise ContractError('INVALID_CHECKER_REGISTRATION')
        if not callable(verify) or not all(isinstance(v, str) and v for v in [metric_id, value_key]):
            raise ContractError('INVALID_CHECKER_REGISTRATION')
        if not isinstance(scope, dict) or set(scope) != {'solution', 'proof'} or any(not isinstance(v, str) or not v for v in scope.values()):
            raise ContractError('INVALID_CHECKER_SCOPE')
        key = (reference['id'], reference['version'])
        if key in self._checks:
            raise ContractError('DUPLICATE_CHECKER')
        self._checks[key] = ProfileCheck(verify, deepcopy(scope), metric_id, value_key, deepcopy(identity))

    def resolve(self, reference):
        entry = self._checks.get((reference['id'], reference['version']))
        if entry is None:
            raise ContractError('UNSUPPORTED_PROFILE')
        return ProfileCheck(entry.verify, deepcopy(entry.scope), entry.metric_id, entry.value_key, deepcopy(entry.identity))


def builtin_checkers():
    registry = CheckerRegistry()
    metrics = {'routing.basic': 'minimize_total_route_cost', 'routing.coordinates': 'minimize_total_route_cost',
               'assignment.fixture': 'cost', 'worker.scheduling': 'total_cost', 'inventory.replenishment': 'total_cost'}
    for (identifier, version), verify in CHECKERS.items():
        registry.register({'id': identifier, 'version': version}, verify,
                          scope=SCOPES[identifier], metric_id=metrics[identifier], value_key='total_cost',
                          identity={'id': 'ocp-conformance-candidate', 'version': '0.1.0'})
    return registry


def load_registry(factory=None):
    """Load only a host-selected, already installed MODULE:FACTORY."""
    if factory is None:
        return builtin_checkers()
    if not isinstance(factory, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*', factory):
        raise ContractError('INVALID_CHECKER_FACTORY')
    module, function = factory.split(':')
    try:
        value = getattr(import_module(module), function)()
    except Exception as error:
        raise ContractError('INVALID_CHECKER_FACTORY') from error
    if not isinstance(value, CheckerRegistry):
        raise ContractError('INVALID_CHECKER_FACTORY')
    return value


def digest(value):
    json_values(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def check(status, reason, **details):
    return {'status': status, 'reason': reason, **details}


def assess(request, response, *, mode='full', registry=None):
    """Report exactly what was checked; PASS is bounded transcript evidence.

    full: check any optimal/infeasible claim with the existing profile checker.
    solution: validate the original envelope and check the supplied solution and
    objective, without attempting its proof. A claimed proof remains PARTIAL.
    Neither mode mutates the transcript or attests execution by an artifact.
    """
    if mode not in ('full', 'solution'):
        raise ValueError('UNSUPPORTED_ASSESSMENT_MODE')
    names = ('structure_and_semantics', 'feasibility', 'objective_recomputation', 'optimality', 'infeasibility')
    checks = {name: check('NOT_CHECKED', 'No successful check yet.') for name in names}
    checks['objective_recomputation']['value'] = None
    checks['execution_attestation'] = check('NOT_CHECKED', 'An offline transcript cannot prove which artifact ran or certify an engine.')
    report = {'report_id': 'ocp.verification-scope', 'report_version': REPORT_VERSION, 'mode': mode, 'status': 'FAIL',
              'checker': {'id': 'ocp-conformance-candidate', 'version': '0.1.0'}, 'checks': checks,
              'scope': 'Independent profile transcript checks only; no engine certification, external acceptance or execution attestation.'}
    try:
        report['request_sha256'] = digest(request)
        report['response_sha256'] = digest(response)
        validate_message(request); validate_message(response)
        if request['kind'] != 'request' or response['kind'] != 'result':
            raise ContractError('INVALID_TRANSCRIPT')
        ref = request['domain_profile']
        entry = (registry if registry is not None else builtin_checkers()).resolve(ref)
        checker = entry.verify
        for field in ('request_id', 'capability', 'domain_profile', 'execution_profile'):
            if request[field] != response[field]: raise ContractError('RESULT_MISMATCH')
        if request['configuration'] != response['effective_configuration']: raise ContractError('RESULT_MISMATCH')
        report.update(domain_profile=deepcopy(ref), response_status=response['status'], profile_scope=entry.scope)
        report['checker'] = entry.identity
        claimed = response['status'] if response['status'] in ('optimal', 'infeasible') else None
        report['claim_requires_proof'] = claimed
        # A private projection lets the strict checker verify solution semantics
        # without running its proof oracle. The original is validated first,
        # preserved, hashed above, and never returned as a downgraded response.
        projected = deepcopy(response)
        if claimed:
            projected.update(status='feasible' if claimed == 'optimal' else 'unknown', proof=None)
        measured = checker(deepcopy(request), projected)
        if (measured is None) != (response['solution'] is None): raise ContractError('INVALID_CHECKER_REPORT')
        if measured is not None:
            if not isinstance(measured, dict) or measured.get('feasible') is not True or type(measured.get(entry.value_key)) not in (int, float):
                raise ContractError('INVALID_CHECKER_REPORT')
            json_values(measured)
        checks['structure_and_semantics'] = check('PASS', 'Original envelope, request identity, configuration and solution/evaluation semantics; proof claim is a separate check.')
        if measured is None:
            checks['feasibility'] = check('NOT_APPLICABLE', 'No solution was supplied. This is not evidence of infeasibility.', constraints_checked=[])
            checks['objective_recomputation'] = check('NOT_APPLICABLE', 'No solution/cost available; null is preserved.', value=None)
        else:
            checks['feasibility'] = check('PASS', 'Supplied solution satisfies the profile checks.',
                                          constraints_checked=[c['id'] for c in response['constraints']])
            metrics = [m for m in response['metrics'] if m['id'] == entry.metric_id]
            if len(metrics) != 1 or metrics[0]['status'] != 'evaluated' or metrics[0]['value'] != measured[entry.value_key]:
                raise ContractError('EVALUATION_MISMATCH')
            metric = metrics[0]
            checks['objective_recomputation'] = check('PASS', 'Objective recomputed by the independent checker and matched to the declared metric.',
                                                       value=measured[entry.value_key], definition=metric['definition'], unit=metric['unit'])
        for name, status in (('optimality', 'optimal'), ('infeasibility', 'infeasible')):
            checks[name] = check('NOT_CLAIMED', 'The response does not make this claim.')
            if claimed == status:
                checks[name] = check('NOT_CHECKED', 'The proof claim has not been independently verified.')
        if not claimed:
            report['status'] = 'PASS'
            return report
        dimension = 'optimality' if claimed == 'optimal' else 'infeasibility'
        if mode == 'solution':
            report['status'] = 'PARTIAL'
            checks[dimension] = check('NOT_CHECKED', 'Solution-only mode deliberately does not verify this claim. Do not report it as proven.')
            return report
        try:
            checker(deepcopy(request), deepcopy(response))
        except ContractError as error:
            unsupported = error.code in ('ORACLE_SCOPE_EXCEEDED', 'UNTESTED_PROOF_CLAIM')
            report['status'] = 'INCOMPLETE' if unsupported else 'FAIL'
            checks[dimension] = check('UNSUPPORTED' if unsupported else 'FAIL', error.code)
        else:
            report['status'] = 'PASS'
            checks[dimension] = check('PASS', 'Claim independently rederived by the profile checker within its documented scope; not general certificate validation.',
                                      method=response['proof']['method'], evidence_validation='Only fields defined by this profile checker; arbitrary proof payloads are not certified.')
        return report
    except ContractError as error:
        checks['structure_and_semantics'] = check('FAIL', error.code)
        return report
    except Exception:
        checks['structure_and_semantics'] = check('FAIL', 'CHECKER_ERROR')
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', required=True, help='JSON containing request and response; existing report fields are ignored')
    parser.add_argument('--mode', choices=('full', 'solution'), default='full')
    parser.add_argument('--checker-factory', help='Trusted installed MODULE:FACTORY; never taken from a transcript')
    args = parser.parse_args()
    try:
        with Path(args.transcript).open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ContractError('TRANSCRIPT_TOO_LARGE')
        transcript = parse_json(raw.decode())
        result = assess(transcript['request'], transcript['response'], mode=args.mode, registry=load_registry(args.checker_factory))
    except (ContractError, OSError, UnicodeError, KeyError, TypeError):
        result = {'status': 'FAIL', 'reason': 'INVALID_TRANSCRIPT_INPUT'}
    print(json.dumps(result, allow_nan=False))
    return 0 if result['status'] == 'PASS' else 2 if result['status'] in ('PARTIAL', 'INCOMPLETE') else 1


if __name__ == '__main__':
    # Factories import CheckerRegistry from the package, not from __main__.
    from .assessment import main as installed_main
    raise SystemExit(installed_main())
