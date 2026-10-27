"""Additive verification-scope report, separate from the Core wire contract.

No solver/provider imports or execution. Existing strict transcript checkers
remain unchanged. Solution-only assessment never verifies a proof claim.
"""
import argparse
from copy import deepcopy
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


def digest(value):
    json_values(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def check(status, reason, **details):
    return {'status': status, 'reason': reason, **details}


def assess(request, response, *, mode='full'):
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
        checker = CHECKERS.get((ref['id'], ref['version']))
        if checker is None:
            raise ContractError('UNSUPPORTED_PROFILE')
        report.update(domain_profile=deepcopy(ref), response_status=response['status'], profile_scope=deepcopy(SCOPES[ref['id']]))
        claimed = response['status'] if response['status'] in ('optimal', 'infeasible') else None
        report['claim_requires_proof'] = claimed
        # A private projection lets the strict checker verify solution semantics
        # without running its proof oracle. The original is validated first,
        # preserved, hashed above, and never returned as a downgraded response.
        projected = deepcopy(response)
        if claimed:
            projected.update(status='feasible' if claimed == 'optimal' else 'unknown', proof=None)
        measured = checker(request, projected)
        checks['structure_and_semantics'] = check('PASS', 'Original envelope, request identity, configuration and solution/evaluation semantics; proof claim is a separate check.')
        if measured is None:
            checks['feasibility'] = check('NOT_APPLICABLE', 'No solution was supplied. This is not evidence of infeasibility.', constraints_checked=[])
            checks['objective_recomputation'] = check('NOT_APPLICABLE', 'No solution/cost available; null is preserved.', value=None)
        else:
            checks['feasibility'] = check('PASS', 'Supplied solution satisfies the profile checks.',
                                          constraints_checked=[c['id'] for c in response['constraints']])
            metric = response['metrics'][0]
            checks['objective_recomputation'] = check('PASS', 'Cost recomputed by the independent checker and matched to the declared metric.',
                                                       value=measured['total_cost'], definition=metric['definition'], unit=metric['unit'])
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
            checker(request, response)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', required=True, help='JSON containing request and response; existing report fields are ignored')
    parser.add_argument('--mode', choices=('full', 'solution'), default='full')
    args = parser.parse_args()
    try:
        with Path(args.transcript).open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ContractError('TRANSCRIPT_TOO_LARGE')
        transcript = parse_json(raw.decode())
        result = assess(transcript['request'], transcript['response'], mode=args.mode)
    except (ContractError, OSError, UnicodeError, KeyError, TypeError):
        result = {'status': 'FAIL', 'reason': 'INVALID_TRANSCRIPT_INPUT'}
    print(json.dumps(result, allow_nan=False))
    return 0 if result['status'] == 'PASS' else 2 if result['status'] in ('PARTIAL', 'INCOMPLETE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
