"""Opt-in preparation records and checked explanation facts, separate from v1.

No natural-language parser or automatic plugin discovery.
Only host-configured clients, store and checker registry are used.
"""
from copy import deepcopy
from threading import RLock

from ocp_candidate.native import NativeError

from .native_evidence_registry import FEATURE_VERSION as EVIDENCE_VERSION


def compare_facts(current, request, baseline, before):
    """Arithmetic on already checked facts with explicit comparison guards."""
    comparison = {'status': 'UNAVAILABLE', 'difference': None,
                  'direction': 'current_minus_baseline',
                  'scope': 'Arithmetic difference of two recorded objectives, not a causal savings claim.'}
    if current['facts'] is None or baseline['facts'] is None:
        comparison['reason'] = 'UNVERIFIED_RESULT'
    else:
        a, b = current['facts']['objective'], baseline['facts']['objective']
        if a['value'] is None or b['value'] is None:
            comparison['reason'] = 'NO_OBJECTIVE'
        elif (any(request[k] != before[k] for k in ('domain_profile', 'execution_profile', 'configuration'))
              or any(a[k] != b[k] for k in ('definition', 'unit'))):
            comparison['reason'] = 'INCOMPARABLE_OBJECTIVES'
        else:
            comparison.update(status='VERIFIED', difference=a['value'] - b['value'], unit=a['unit'],
                              reason='TWO_INDEPENDENTLY_RECOMPUTED_OBJECTIVES')
    return comparison




class EvidenceService:
    """Process-local bounded records, scoped by host-supplied tenant and domain."""

    def __init__(self, clients, store, *, registry=None, evidence_registry=None, max_records=128):
        from conformance.assessment import builtin_checkers
        if type(max_records) is not int or not 1 <= max_records <= 1024:
            raise ValueError('INVALID_RECORD_LIMIT')
        self.clients, self.store = dict(clients), store
        self.registry = builtin_checkers() if registry is None else registry
        from .native_evidence_registry import builtin_evidence
        self.evidence_registry = (builtin_evidence() if evidence_registry is None else evidence_registry).snapshot()
        self.max_records, self._records, self._lock = max_records, {}, RLock()
        from .native_evidence_validation import ValidationRecords
        self.validation = ValidationRecords(self.clients, version=EVIDENCE_VERSION, max_records=max_records)

    def context(self, domain=None, catalog=None):
        from .native_evidence_guidance import input_policy, constraint_scope, comparison_inputs
        profile = deepcopy(catalog.get('domainProfile')) if catalog is not None else None
        from .native_evidence_registry import IDENTITY_SCHEMA
        handler = self.evidence_registry.resolve(profile) if profile else None
        return {'version': EVIDENCE_VERSION, 'prepare_tool': 'ocp_native_prepare',
                'explain_tool': 'ocp_native_explain',
                'mapped_profile': deepcopy(profile) if handler and handler.mapping_supported else None,
                'capability_scope': {'configured_domains': list(self.clients), 'selected_domain': domain,
                    'selected_profile': profile, 'catalog_scope': 'SELECTED_DOMAIN_ONLY' if domain else 'DOMAIN_INDEX',
                    'direct_support_source': 'The selected provider catalog; other configured domains have their own catalogs.',
                    'mapping_scope': 'Optional preparation mappings, separate from direct provider support.',
                    'selected_mapping_support': ('SELECT_DOMAIN' if domain is None else
                                                 'AVAILABLE' if handler and handler.mapping_supported else 'NOT_AVAILABLE'),
                    'identity_preparation': 'Available for valid configured domain requests with requirements=[].'},
                'input_policy': input_policy(catalog),
                'constraint_scope': constraint_scope(catalog),
                'comparison_inputs': comparison_inputs(),
                'requirements_schema': deepcopy(handler.requirements_schema if handler else IDENTITY_SCHEMA),
                'selected_evidence_handler': handler.description() if handler else None,
                'handler_scope': 'Explicit trusted host registration; custom handler code is not certified by registration.',
                'request_shape': 'Full Core request: copy catalog.requestTemplate and replace its input. Never send input alone.',
                'support_scope': 'Provider catalog describes direct engine support; prepare adds the checked mappings listed here.',
                'record_lifetime': 'current server process; keep the preparation ID',
                'scope': 'Structured requirements and stored results. Source text interpretation and extra host prose are NOT_CHECKED.',
                'workflow': 'For extra requirements, prepare with detail=compact, validate and submit the returned problem unchanged. '
                            'For a plain request, validate and submit directly. After a terminal job, explain returns the solution '
                            'and reruns independent verification; separate result/verify/evaluate calls are not needed for the same explanation. '
                            'Include preparation_id when prepared, and two completed job IDs for comparisons. '
                            'Read capability_scope before describing server-wide support. '
                            'Use explanation_basis for source references; an absent baseline means comparison is unavailable. '
                            'Submit revalidates the exact input and records whether an explicit validate call was observed. '
                            'Use the returned facts and count scopes; an unsupported required goal needs a supporting profile.'}

    def validate(self, domain, problem, *, tenant):
        return self.validation.validate(domain, problem, tenant=tenant)

    def submit(self, domain, problem, *, tenant, idempotency_key):
        return self.validation.submit(domain, problem, tenant=tenant, idempotency_key=idempotency_key)

    def _client(self, domain):
        if domain not in self.clients:
            raise NativeError('UNSUPPORTED_DOMAIN')
        return self.clients[domain]

    @staticmethod
    def _validation_error(code, checked, *, stage):
        raise NativeError(code, body={'code': code, 'message':
            ('Use the full catalog.requestTemplate with input filled; keep the envelope and correct the listed fields.'
             if stage == 'original' else 'Prepared input exceeds the selected profile; inspect the listed fields.'),
            'requestId': 'mcp', 'retryable': False, 'issues': deepcopy(checked.get('issues', []))})

    def prepare(self, domain, problem, requirements, source_text, *, tenant, detail='full'):
        from conformance.assessment import digest
        from conformance.core_contract import ContractError
        from conformance.preparation import validate_requirements, verify_preparation
        from conformance.planning import integral_numbers
        from .native_evidence_facts import mapping_facts
        client = self._client(domain)
        if detail not in ('full', 'compact'):
            raise NativeError('INVALID_EVIDENCE_DETAIL')
        if not isinstance(source_text, str) or not source_text.strip() or len(source_text) > 8192:
            raise NativeError('INVALID_SOURCE_TEXT')
        original, rules = deepcopy(problem), deepcopy(requirements)
        from .native_evidence_registry import invoke, check_preparation
        from jsonschema import Draft202012Validator
        handler = self.evidence_registry.resolve(original.get('domain_profile') if isinstance(original, dict) else None)
        catalog_hash = digest(client.capabilities())
        try:
            try:
                if handler:
                    if rules and not handler.mapping_supported:
                        raise ContractError('UNSUPPORTED_REQUIREMENT')
                    invoke(handler.validate, original, rules)
                    if not Draft202012Validator(handler.requirements_schema).is_valid(rules):
                        raise ContractError('INVALID_REQUIREMENT')
                else:
                    if rules:
                        raise ContractError('UNSUPPORTED_MAPPING_PROFILE')
                    validate_requirements(original, rules)
            except ContractError as error:
                if error.code in ('SCHEMA_INVALID', 'INVALID_INPUT', 'INVALID_CONFIGURATION',
                                  'INVALID_TASK', 'INVALID_AVAILABILITY', 'DUPLICATE_ID'):
                    checked = client.validate(deepcopy(original))
                    if checked.get('valid') is not True:
                        self._validation_error(error.code, checked, stage='original')
                raise
            checked = client.validate(deepcopy(original))
            if checked.get('valid') is not True:
                self._validation_error('INVALID_ORIGINAL_PROBLEM', checked, stage='original')
            if handler:
                mapped = invoke(handler.prepare, original, integral_numbers(rules))
                if not isinstance(mapped, (list, tuple)) or len(mapped) != 2:
                    raise ContractError('INVALID_MAPPING_REPORT')
                prepared, mapping = mapped
            else:
                prepared, mapping = deepcopy(original), {'id': 'identity', 'version': EVIDENCE_VERSION}
            if (not isinstance(mapping, dict) or set(mapping) != {'id', 'version'} or
                    any(not isinstance(v, str) or not v for v in mapping.values())):
                raise ContractError('INVALID_MAPPING_REPORT')
            if not rules and (digest(original) != digest(prepared) or mapping['id'] != 'identity'):
                raise ContractError('PREPARATION_MISMATCH')
            checked = client.validate(deepcopy(prepared))
            if checked.get('valid') is not True:
                self._validation_error('PREPARED_INPUT_OUT_OF_SCOPE', checked, stage='prepared')
            proof = invoke(handler.verify_preparation if handler else verify_preparation, original, rules, prepared)
            check_preparation(proof, original, rules, prepared)
            if digest(client.capabilities()) != catalog_hash:
                raise ContractError('PREPARATION_CATALOG_CHANGED')
            record = {'version': EVIDENCE_VERSION, 'domain': domain, 'source_text': source_text,
                      'handler': handler.description() if handler else None, 'catalog_sha256': catalog_hash,
                      'source_text_interpretation': 'NOT_CHECKED', 'original_problem': original,
                      'requirements': rules, 'problem': prepared, 'mapping': mapping,
                      'verification': proof, 'mapping_facts': invoke(handler.mapping_facts if handler else mapping_facts,
                                                                   original, rules, proof)}
            identifier = digest(record)
        except ContractError as error:
            raise NativeError(error.code) from None
        key = (tenant, domain, identifier)
        with self._lock:
            if key not in self._records and len(self._records) >= self.max_records:
                raise NativeError('PREPARATION_RECORD_LIMIT')
            self._records[key] = deepcopy(record)
        returned = deepcopy(record)
        if detail == 'compact':
            for key in ('original_problem', 'source_text'):
                returned.pop(key)
        return {'status': 'READY', 'preparation_id': identifier, 'detail': detail, **returned}

    def _preparation(self, domain, identifier, job, *, tenant):
        from conformance.assessment import digest
        from conformance.core_contract import ContractError
        from conformance.preparation import verify_preparation
        from .native_evidence_facts import mapping_facts
        if identifier is None:
            return {'status': 'NOT_PROVIDED', 'scope': 'Submitted problem only; original requirements are not linked.'}
        with self._lock:
            record = deepcopy(self._records.get((tenant, domain, identifier)))
        if record is None:
            raise NativeError('PREPARATION_NOT_FOUND')
        if digest(record) != identifier or digest(job.problem) != digest(record['problem']):
            raise NativeError('PREPARATION_JOB_MISMATCH')
        try:
            from .native_evidence_registry import invoke, check_preparation
            handler = self.evidence_registry.resolve(job.problem['domain_profile'])
            if record['handler'] != (handler.description() if handler else None):
                raise ContractError('PREPARATION_HANDLER_CHANGED')
            if record['catalog_sha256'] != digest(self._client(domain).capabilities()):
                raise ContractError('PREPARATION_CATALOG_CHANGED')
            proof = invoke(handler.verify_preparation if handler else verify_preparation,
                           record['original_problem'], record['requirements'], job.problem)
            check_preparation(proof, record['original_problem'], record['requirements'], job.problem)
            details = invoke(handler.mapping_facts if handler else mapping_facts,
                             record['original_problem'], record['requirements'], proof)
            if digest(details) != digest(record['mapping_facts']):
                raise ContractError('PREPARATION_FACTS_CHANGED')
        except ContractError as error:
            raise NativeError(error.code) from None
        return {'status': 'PASS', 'preparation_id': identifier, 'source_text': record['source_text'],
                'source_text_interpretation': 'NOT_CHECKED', 'mapping': record['mapping'],
                'requirements': record['requirements'], 'verification': proof,
                'handler': record['handler'], 'catalog_sha256': record['catalog_sha256'], 'mapping_facts': details}

    def _explain_one(self, domain, job_id, preparation_id, *, tenant):
        from conformance.assessment import assess
        from .native_verification import completed_job
        self._client(domain)
        job = completed_job(self.store, domain, job_id, tenant=tenant)
        preparation = self._preparation(domain, preparation_id, job, tenant=tenant)
        report = assess(job.problem, job.result, registry=self.registry)
        facts = None
        if report['status'] == 'PASS':
            checks = report['checks']
            objective = checks['objective_recomputation']
            from .native_evidence_registry import invoke
            from conformance.assessment import digest
            from conformance.core_contract import ContractError
            handler = self.evidence_registry.resolve(job.problem['domain_profile'])
            details = None
            if handler:
                try:
                    data = invoke(handler.solution_facts, job.problem, job.result, objective['value'], preparation)
                    checked = invoke(handler.verify_solution_facts, job.problem, job.result, objective['value'], preparation, data)
                    if (not isinstance(checked, dict) or checked.get('status') != 'PASS' or
                            checked.get('request_sha256') != digest(job.problem) or
                            checked.get('response_sha256') != digest(job.result) or
                            checked.get('details_sha256') != digest(data) or
                            not isinstance(checked.get('checker'), dict) or
                            any(not isinstance(checked['checker'].get(k), str) or not checked['checker'][k] for k in ('id', 'version'))):
                        raise ContractError('INVALID_DETAIL_REPORT')
                    details = {'handler': handler.description(), 'data': data, 'verification': checked}
                except ContractError as error:
                    raise NativeError(error.code) from None
            facts = {'result_status': job.result['status'],
                     'solution': deepcopy(job.result['solution']),
                     'objective': {'value': objective['value'], 'unit': objective.get('unit'),
                                   'definition': objective.get('definition'), 'check_status': objective['status']},
                     'optimality_verified': checks['optimality']['status'] == 'PASS',
                     'infeasibility_verified': checks['infeasibility']['status'] == 'PASS',
                     'constraints': deepcopy(job.result['constraints']),
                     'termination': deepcopy(job.result['termination']),
                     'domain_details': details,
                     # Backward-compatible alias; extension details use domain_details.
                     'worker_assignment': (details['data'] if details and
                         handler.identity == {'id': 'ocp.worker-evidence', 'version': '0.1.0'} and
                         job.problem['domain_profile'] == {'id': 'worker.scheduling', 'version': '0.1.0'} else None)}
        return {'version': EVIDENCE_VERSION, 'job_id': job.id, 'job_status': job.status.value,
                'status': 'VERIFIED' if facts is not None else 'UNVERIFIED',
                'verification': report, 'preparation': preparation, 'facts': facts,
                'input_validation': self.validation.for_job(domain, job.id, job.problem, tenant=tenant),
                'scope': 'Only these stored request/result facts are checked. Other assignments and host-written prose are not verified.'}, job.problem

    def explain(self, domain, job_id, preparation_id=None, baseline_job_id=None,
                baseline_preparation_id=None, *, tenant):
        if baseline_preparation_id is not None and baseline_job_id is None:
            raise NativeError('BASELINE_JOB_REQUIRED')
        current, request = self._explain_one(domain, job_id, preparation_id, tenant=tenant)
        from .native_evidence_facts import explanation_basis
        if baseline_job_id is None:
            from .native_evidence_guidance import comparison_inputs
            comparison = {'status': 'UNAVAILABLE', 'difference': None, 'reason': 'BASELINE_NOT_PROVIDED',
                          'accepted_inputs': comparison_inputs(),
                          'scope': 'Only the current job was checked; no baseline cost or alternative was computed.'}
            return {**current, 'comparison': comparison,
                    'explanation_basis': explanation_basis(current, None, comparison)}
        baseline, before = self._explain_one(domain, baseline_job_id, baseline_preparation_id, tenant=tenant)
        comparison = compare_facts(current, request, baseline, before)
        return {**current, 'baseline': baseline, 'comparison': comparison,
                'explanation_basis': explanation_basis(current, baseline, comparison)}
