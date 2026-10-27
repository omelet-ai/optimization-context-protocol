"""Planning transcript envelope checks. No provider or solver imports."""
from functools import lru_cache
from jsonschema import Draft202012Validator
from .core_contract import SCHEMAS, ContractError, parse_json, validate_message

def integral_numbers(value):
    if type(value) is float and value.is_integer():return int(value)
    if type(value) is list:return [integral_numbers(x) for x in value]
    if type(value) is dict:return {k:integral_numbers(v) for k,v in value.items()}
    return value

@lru_cache(maxsize=16)
def definition(stem,kind):
    return parse_json((SCHEMAS/(stem+'-'+kind+'-0.1.schema.json')).read_text())

def shape(stem,kind,value):
    if not Draft202012Validator(definition(stem,kind)).is_valid(value):raise ContractError('INVALID_'+kind.upper())

def verify(profile,request,result):
    validate_message(request);validate_message(result)
    if request['kind']!='request' or result['kind']!='result':raise ContractError('INVALID_RESULT')
    if request['domain_profile']!={'id':profile.ID,'version':'0.1.0'} or request['execution_profile']!={'id':'execution.sync','version':'0.1.0'}:raise ContractError('VERSION_MISMATCH')
    for key in ('request_id','capability','domain_profile','execution_profile'):
        if request[key]!=result[key]:raise ContractError('RESULT_MISMATCH')
    shape(profile.STEM,'configuration',request['configuration'])
    if request['configuration']!=result['effective_configuration']:raise ContractError('RESULT_MISMATCH')
    if not 1<=request['budget']['time_limit_ms']<=5000:raise ContractError('BUDGET_OUT_OF_SCOPE')
    p=request['input'];profile.validate_problem(p)
    measured=None
    if result['solution'] is not None:
        measured=profile.evaluate(p,result['solution'])
        if not measured['feasible']:raise ContractError('INFEASIBLE_SOLUTION')
        metrics=result['metrics'];cs=result['constraints']
        if len(metrics)!=1 or len(cs)!=len(request['configuration']['constraints']):raise ContractError('EVALUATION_MISMATCH')
        expected={'id':'total_cost','role':'optimized','definition':profile.ID+'.total_cost.v1','unit':'cost_unit','status':'evaluated','value':measured['total_cost'],'reason':None}
        if any(metrics[0].get(k)!=v for k,v in expected.items()):raise ContractError('EVALUATION_MISMATCH')
        if {c['id'] for c in cs}!=set(request['configuration']['constraints']):raise ContractError('EVALUATION_MISMATCH')
        for c in cs:
            expected={'role':'enforced','definition':profile.ID+'.'+c['id']+'.v1','unit':'count','status':'evaluated','violation':measured['violations'][c['id']],'satisfied':True,'reason':None}
            if any(c.get(k)!=v for k,v in expected.items()):raise ContractError('EVALUATION_MISMATCH')
    elif result['metrics'] or result['constraints']:raise ContractError('EVALUATION_WITHOUT_SOLUTION')
    if result['status'] in ('optimal','infeasible'):
        optimum=profile.exhaustive_optimum(p)
        expected={'claim':result['status'],'method':profile.PROOF,'scope':profile.ID+':0.1.0','evidence':{'objective':optimum}}
        evidence=result['proof']['evidence'].get('objective')
        if result['proof']!=expected or (evidence is not None and (type(evidence) not in (int,float) or evidence!=int(evidence))):raise ContractError('UNVERIFIED_PROOF')
        if result['status']=='optimal' and (optimum is None or measured['total_cost']!=optimum):raise ContractError('UNVERIFIED_PROOF')
        if result['status']=='infeasible' and optimum is not None:raise ContractError('UNVERIFIED_PROOF')
    return measured
