"""Core adapter shared by explicitly registered planning profiles."""
from copy import deepcopy
import time
from ocp_candidate.contract import OCPError, envelope, failure, schema, validate

def integer_values(value):
    # JSON Schema integer includes 1.0; normalize validated integral numbers.
    if isinstance(value,dict):return {k:integer_values(v) for k,v in value.items()}
    if isinstance(value,list):return [integer_values(v) for v in value]
    return int(value) if type(value) is float and value.is_integer() else value

SYNC={'id':'execution.sync','version':'0.1.0'}

class PlanningAdapter:
    def __init__(self, profile, *, clock=time.monotonic):
        self.profile=profile;self.clock=clock
        self.domain={'id':profile.ID,'version':'0.1.0'}
        self.identity={'id':profile.ID+'.reference','version':'0.1.0'}

    def configuration(self, value=None):
        expected=deepcopy(schema(self.profile.STEM+'-configuration')['const'])
        if value is not None:validate(self.profile.STEM+'-configuration',value,'UNSUPPORTED_CONFIGURATION')
        return expected

    def describe(self):
        p=self.profile
        return {'core_version':'0.1.0','kind':'capability','capability':deepcopy(self.identity),'domain_profile':deepcopy(self.domain),
                'execution_profiles':[SYNC.copy()],'bindings':[{'id':'binding.in_process','version':'0.1.0'}],
                'environments':[{'id':'environment.local','version':'0.1.0'}],
                'objectives':[{'id':'total_cost','direction':'minimize','role':'optimized','definition':p.ID+'.total_cost.v1','unit':'cost_unit'}],
                'constraints':[{'id':c,'kind':'hard','role':'enforced','definition':p.ID+'.'+c+'.v1','unit':'count'} for c in self.configuration()['constraints']],
                'configuration_schema':deepcopy(schema(p.STEM+'-configuration')),'input_schema_id':schema(p.STEM+'-input')['$id'],
                'solution_schema_id':schema(p.STEM+'-solution')['$id'],'defaults':self.configuration(),'limitations':list(p.LIMITATIONS)}

    def requirements(self,configuration):
        try:
            return {'core_version':'0.1.0','kind':'requirements','capability':deepcopy(self.identity),'domain_profile':deepcopy(self.domain),
                    'effective_configuration':self.configuration(configuration),'input_schema_id':schema(self.profile.STEM+'-input')['$id'],
                    'required_fields':deepcopy(self.profile.REQUIREMENTS)}
        except OCPError as e:return failure(None,e)

    def check_request(self,r):
        envelope(r)
        if r['kind']!='request':raise OCPError('INVALID_REQUEST')
        if r['domain_profile']!=self.domain or r['execution_profile']!=SYNC or r['capability']!=self.identity:raise OCPError('VERSION_MISMATCH')
        self.configuration(r['configuration'])
        if not 1<=r['budget']['time_limit_ms']<=5000:raise OCPError('LIMIT_EXCEEDED','/budget/time_limit_ms')
        validate(self.profile.STEM+'-input',r['input']);self.profile.validate_problem(r['input'])

    def validate(self,request):
        rid=request.get('request_id') if isinstance(request,dict) else None
        if not isinstance(rid,str) or not 0<len(rid)<=128:rid='invalid-request'
        issues=[]
        try:self.check_request(request)
        except OCPError as e:issues=[{'code':e.code,'path':e.path,'message':e.message}]
        return {'core_version':'0.1.0','kind':'validation','request_id':rid,'valid':not issues,'issues':issues}

    def fields(self,problem,solution):
        validate(self.profile.STEM+'-solution',solution,'INVALID_SOLUTION')
        cost,violations=self.profile.evaluate(integer_values(problem),integer_values(solution))
        metric={'id':'total_cost','role':'optimized','definition':self.profile.ID+'.total_cost.v1','unit':'cost_unit',
                'source':'engine','status':'evaluated','value':cost,'reason':None}
        constraints=[{'id':c,'role':'enforced','definition':self.profile.ID+'.'+c+'.v1','unit':'count',
                      'source':'engine','status':'evaluated','violation':violations[c],'satisfied':violations[c]==0,'reason':None}
                     for c in self.configuration()['constraints']]
        return [metric],constraints

    def execute(self,request):
        rid=request.get('request_id') if isinstance(request,dict) else None
        try:
            self.check_request(request);r=deepcopy(request);r['input']=integer_values(r['input'])
            solution,completed=self.profile.solve(r['input'],self.clock()+r['budget']['time_limit_ms']/1000,self.clock)
            metrics,cons=self.fields(r['input'],solution) if solution is not None else ([],[])
            if any(not c['satisfied'] for c in cons):raise OCPError('INVALID_ENGINE_RESULT')
            status=('optimal' if solution is not None else 'infeasible') if completed else ('feasible' if solution is not None else 'unknown')
            proof={'claim':status,'method':self.profile.PROOF,'scope':self.profile.ID+':0.1.0',
                   'evidence':{'objective':metrics[0]['value'] if metrics else None}} if completed else None
            response={'core_version':'0.1.0','kind':'result','request_id':rid,'capability':deepcopy(self.identity),
                'domain_profile':deepcopy(self.domain),'execution_profile':SYNC.copy(),'effective_configuration':r['configuration'],
                'status':status,'termination':'completed' if completed else 'time_limit','solution':solution,'proof':proof,
                'metrics':metrics,'constraints':cons,'provenance':{'implementation':{'id':'ocp-candidate.planning-adapter','version':'0.1.0'},
                'engine':{'id':self.profile.ENGINE,'version':'0.1.0'},'request_id':rid,'limitations':list(self.profile.LIMITATIONS)}}
            envelope(response);return response
        except OCPError as e:return failure(rid,e)
        except Exception:return failure(rid,OCPError('EXECUTION_ERROR',message='Planning provider failed'))

    def evaluate(self,request,solution):
        rid=request.get('request_id') if isinstance(request,dict) else None
        try:
            self.check_request(request);metrics,cons=self.fields(request['input'],solution)
            return {'core_version':'0.1.0','kind':'evaluation','request_id':rid,'capability':deepcopy(self.identity),
                'domain_profile':deepcopy(self.domain),'metrics':metrics,'constraints':cons,
                'evaluator':{'id':'ocp-candidate.planning-evaluator','version':'0.1.0'},
                'limitations':['Provider evaluation reuses provider logic; use the separately packaged independent checker.']}
        except OCPError as e:return failure(rid,e)
