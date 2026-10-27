"""Explicit, offline profile context registration; schemas never fetched by URI."""
from copy import deepcopy
from importlib.resources import files
from jsonschema import Draft202012Validator
from .contract import OCPError, parse_json, schema

class ProfileRegistry:
    def __init__(self):self._profiles={}

    def register(self, reference, input_schema, solution_schema, semantics):
        if not isinstance(reference,dict) or set(reference)!={'id','version'} or any(not isinstance(v,str) or not v for v in reference.values()):raise OCPError('INVALID_PROFILE_REGISTRATION')
        key=(reference['id'],reference['version'])
        if key in self._profiles:raise OCPError('DUPLICATE_PROFILE')
        def local_refs(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('$ref','$dynamicRef') and (not isinstance(v,str) or not v.startswith('#')):raise OCPError('EXTERNAL_SCHEMA_REFERENCE')
                    local_refs(v)
            elif isinstance(value,list):
                for v in value:local_refs(v)
        for data in (input_schema,solution_schema):
            local_refs(data);Draft202012Validator.check_schema(data)
            if not isinstance(data.get('$id'),str) or not data['$id']:raise OCPError('MISSING_SCHEMA_ID')
        if not isinstance(semantics,list) or not semantics or any(not isinstance(s,str) or not s for s in semantics):raise OCPError('INVALID_PROFILE_SEMANTICS')
        self._profiles[key]=deepcopy({'input_schema':input_schema,'solution_schema':solution_schema,'profile_semantics':semantics})

    def resolve(self,capability):
        ref=capability['domain_profile'];value=self._profiles.get((ref['id'],ref['version']))
        if value is None:raise OCPError('UNREGISTERED_PROFILE')
        if value['input_schema']['$id']!=capability['input_schema_id'] or value['solution_schema']['$id']!=capability['solution_schema_id']:raise OCPError('SCHEMA_ID_MISMATCH')
        return deepcopy(value)

def packaged_registry():
    registry=ProfileRegistry()
    for p in parse_json(files('ocp_candidate').joinpath('profiles.json').read_text()):
        registry.register(p['reference'],schema(p['input_schema']),schema(p['solution_schema']),p['semantics'])
    return registry
