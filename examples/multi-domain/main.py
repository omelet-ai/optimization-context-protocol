"""One application flow for every explicitly selected reference profile."""
import argparse
import json
from pathlib import Path
from ocp_candidate import Client, parse_json
from ocp_runtime.providers import PROVIDERS, make_provider
from conformance.runner import CHECKERS
from conformance.assessment import assess

def run(profile, problem, request_id):
    adapter=make_provider(profile);client=Client(adapter)
    requirements=client.requirements()
    request=client.request(problem,request_id=request_id)
    validation=adapter.validate(request)
    if not validation['valid']:return {'status':'FAIL','validation':validation,'execute_calls':0}
    response=client.execute(problem,request_id=request_id)
    if response['kind']=='failure':return {'status':'FAIL','response':response,'execute_calls':1}
    ref=request['domain_profile'];checked=CHECKERS[(ref['id'],ref['version'])](request,response)
    evaluation=adapter.evaluate(request,response['solution']) if response['solution'] is not None else None
    return {'status':'PASS','requirements':requirements,'request':request,'response':response,
            'evaluation':evaluation,'independent_check':checked,'verification':assess(request,response),'execute_calls':1,'model_calls':0,
            'solution_found':response['solution'] is not None,'scope':'Local solve and independent check; not model or human acceptance'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=list(PROVIDERS),required=True)
    p.add_argument('--input',required=True);p.add_argument('--request-id',required=True);a=p.parse_args()
    try:
        raw=Path(a.input).read_bytes()
        if len(raw)>131072:raise ValueError('Input too large')
        result=run(a.profile,parse_json(raw.decode()),a.request_id)
    except Exception:
        result={'status':'FAIL','code':'LOCAL_APP_ERROR','hint':'Check profile, input schema and environment; no automatic retry.'}
    print(json.dumps(result,allow_nan=False));return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
