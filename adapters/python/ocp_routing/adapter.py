"""routing.basic provider over an explicitly compatible solver library."""

from copy import deepcopy
from ocp_candidate.contract import OCPError, envelope, failure, schema
from . import profile


class RoutingAdapter:
    def __init__(self, backend):
        self.backend=backend
        self.identity={"id":"routing.reference","version":"0.1.0"}

    def describe(self):
        return {"core_version":"0.1.0","kind":"capability","capability":deepcopy(self.identity),
                "domain_profile":deepcopy(profile.DOMAIN),"execution_profiles":[deepcopy(profile.SYNC)],
                "bindings":[{"id":"binding.in_process","version":"0.1.0"}],
                "environments":[{"id":"environment.local","version":"0.1.0"}],
                "objectives":[{"id":"minimize_total_route_cost","direction":"minimize","role":"optimized",
                               "definition":"routing.basic.total_distance.v1","unit":"meter"}],
                "constraints":[{"id":cid,"kind":"hard","role":"enforced","definition":"routing.basic."+cid+".v1","unit":unit}
                               for cid,unit in [("weight_capacity","kg"),("all_visits_once","count")]],
                "configuration_schema":deepcopy(schema("routing-configuration")),
                "input_schema_id":schema("routing-input")["$id"],"solution_schema_id":schema("routing-solution")["$id"],
                "defaults":profile.configuration(),
                "limitations":["Explicit integer meter matrix, integer kg, single trip, all visits mandatory",
                               "1-16 vehicles, 1-64 visits; solver budget 1-5000 ms",
                               "Only feasible is claimed for a found solution; no general optimality proof",
                               "No remote authentication, tenant isolation, async jobs or hosted trial"]}

    def requirements(self, configuration):
        try:
            selected=profile.configuration(configuration)
            return {"core_version":"0.1.0","kind":"requirements","capability":deepcopy(self.identity),
                    "domain_profile":deepcopy(profile.DOMAIN),"effective_configuration":selected,
                    "input_schema_id":schema("routing-input")["$id"],
                    "required_fields":[{"path":path,"reason":reason,"unit":unit} for path,reason,unit in [
                        ("/depot","All routes start and end here","identifier"),
                        ("/visits","Mandatory visits and demand for capacity","kg"),
                        ("/vehicles","Vehicle identities and hard capacity","kg"),
                        ("/matrix","Objective uses explicit directed edge distances","meter"),
                        ("/load_unit","Demands and capacities must use the same unit","kg")]]}
        except OCPError as exc:
            return failure(None,exc)

    def validate(self, request):
        issues=[]
        request_id=request.get("request_id") if isinstance(request,dict) else None
        if not isinstance(request_id,str) or not request_id:
            request_id="invalid-request"
        try:
            profile.check_request(request,self.identity)
        except OCPError as exc:
            issues=[{"code":exc.code,"path":exc.path,"message":exc.message}]
        return {"core_version":"0.1.0","kind":"validation","request_id":request_id or "invalid-request",
                "valid":not issues,"issues":issues}

    def execute(self, request):
        request_id=request.get("request_id") if isinstance(request,dict) else None
        if not isinstance(request_id,str) or not request_id:
            request_id=None
        try:
            profile.check_request(request,self.identity)
            original=deepcopy(request)
            problem=original["input"]
            demand=sum(v["demand"] for v in problem["visits"])
            capacity=sum(v["capacity"] for v in problem["vehicles"])
            proof=None
            if demand>capacity:
                proof={"claim":"infeasible","method":"total-demand-exceeds-total-capacity","scope":"all mandatory visits",
                       "evidence":{"total_demand":demand,"total_capacity":capacity}}
            elif max(v["demand"] for v in problem["visits"])>max(v["capacity"] for v in problem["vehicles"]):
                proof={"claim":"infeasible","method":"individual-demand-exceeds-all-capacities","scope":"all mandatory visits",
                       "evidence":{"maximum_demand":max(v["demand"] for v in problem["visits"]),"maximum_capacity":max(v["capacity"] for v in problem["vehicles"])}}
            if proof:
                status,solution,termination,metrics,constraints="infeasible",None,"completed",[],[]
            else:
                outcome=self.backend.solve(deepcopy(problem),original["budget"]["time_limit_ms"])
                solution,termination=outcome.solution,outcome.termination
                status="unknown" if solution is None else "feasible"
                metrics,constraints=[],[]
                if solution is not None:
                    metrics,constraints=profile.evaluation_fields(problem,solution,"engine")
                    if any(not c["satisfied"] for c in constraints) or outcome.objective != metrics[0]["value"]:
                        raise OCPError("INVALID_ENGINE_RESULT",message="Engine result violates profile or objective")
            response={"core_version":"0.1.0","kind":"result","request_id":request_id,"capability":deepcopy(self.identity),
                      "domain_profile":deepcopy(profile.DOMAIN),"execution_profile":deepcopy(profile.SYNC),
                      "effective_configuration":deepcopy(original["configuration"]),"status":status,"termination":termination,
                      "solution":solution,"proof":proof,"metrics":metrics,"constraints":constraints,
                      "provenance":{"implementation":{"id":"ocp-candidate.routing-adapter","version":"0.1.0"},
                                    "engine":{"id":self.backend.name,"version":self.backend.version},"request_id":request_id,
                                    "limitations":["Analytic infeasibility check; solver not invoked"] if proof else ["Found solutions are feasible, not certified optimal"]}}
            envelope(response)
            return response
        except OCPError as exc:
            return failure(request_id,exc)
        except Exception:
            return failure(request_id,OCPError("EXECUTION_ERROR",message="Solver execution failed"))

    def evaluate(self, request, solution):
        try:
            profile.check_request(request,self.identity)
            metrics,constraints=profile.evaluation_fields(request["input"],solution)
            return {"core_version":"0.1.0","kind":"evaluation","request_id":request["request_id"],
                    "capability":deepcopy(self.identity),"domain_profile":deepcopy(profile.DOMAIN),"metrics":metrics,"constraints":constraints,
                    "evaluator":{"id":"ocp-candidate.routing-evaluator","version":"0.1.0"},"limitations":["Feasibility and cost evaluation; no optimality proof"]}
        except OCPError as exc:
            rid=request.get("request_id") if isinstance(request,dict) else None
            return failure(rid if isinstance(rid,str) and rid else None,exc)
