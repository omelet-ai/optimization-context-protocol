"""One application, two actual engines, independently checked routing.basic results."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from ocp_candidate import Client, parse_json
from conformance.core_contract import ContractError
from conformance.routing import verify_result
from byo_library import OwnLibraryAdapter


def run_app(adapter, problem, request_id, time_limit_ms=1000):
    """Keep this application flow unchanged when substituting a compatible adapter."""
    client=Client(adapter)
    requirements=client.requirements()
    if requirements["kind"]!="requirements":raise ValueError("Requirements rejected")
    request=client.request(deepcopy(problem),request_id=request_id,time_limit_ms=time_limit_ms)
    validation=adapter.validate(request)
    if not validation["valid"]:raise ValueError("Input rejected: "+json.dumps(validation["issues"]))
    result=client.execute(deepcopy(problem),request_id=request_id,time_limit_ms=time_limit_ms)
    if result["kind"]!="result":raise ValueError("Engine failure: "+json.dumps(result))
    checked=verify_result(request,result)
    evaluation=adapter.evaluate(request,result["solution"]) if result["solution"] is not None else None
    if evaluation is not None and evaluation["kind"]!="evaluation":raise ValueError("Evaluation failed")
    return {"request":request,"response":result,"evaluation":evaluation,"independent_check":checked}


def diagnostics():
    # Controlled synthetic probes are independent of the user's input file.
    problem=parse_json((Path(__file__).with_name("basic-input.json")).read_text())
    adapter=OwnLibraryAdapter()
    trace=run_app(adapter,problem,"diagnostic-baseline")
    checks={}
    bad=deepcopy(problem);bad["matrix"]["unit"]="kilometer"
    invalid=adapter.validate(Client(adapter).request(bad,request_id="unit-probe"))
    if invalid["valid"]:raise ValueError("Unsupported unit was accepted")
    checks["unsupported_unit"]={"rejected":True,"issues":invalid["issues"]}
    for name in ("capacity_violation","missing_visit","wrong_objective"):
        damaged=deepcopy(trace["response"])
        if name=="capacity_violation":
            routes=damaged["solution"]["routes"]
            routes[0]["visits"]=[v["id"] for v in problem["visits"]]
            for route in routes[1:]:route["visits"]=[]
        elif name=="missing_visit":
            next(r for r in damaged["solution"]["routes"] if r["visits"])["visits"].pop()
        else:damaged["metrics"][0]["value"]+=1
        try:verify_result(trace["request"],damaged)
        except ContractError as error:checks[name]={"rejected":True,"code":error.code}
        else:raise ValueError("Independent checker accepted "+name)
    # A real wall-clock deadline in the teaching library, never a mocked timeout.
    names=["hub"]+["stop-"+str(i) for i in range(6)]
    timed={"depot":"hub","load_unit":"kg","visits":[{"id":n,"demand":1} for n in names[1:]],
           "vehicles":[{"id":"v"+str(i),"capacity":6} for i in range(3)],
           "matrix":{"node_ids":names,"unit":"meter","model":"explicit_matrix","rounding":"none",
                     "values":[[0 if i==j else 1 for j in range(7)] for i in range(7)]}}
    outcome=run_app(OwnLibraryAdapter(),timed,"deadline-probe",time_limit_ms=1)
    result=outcome["response"]
    if result["status"] not in {"feasible","unknown"}:raise ValueError("Deadline promoted to a proof")
    checks["deadline"]={"budget_ms":1,"status":result["status"],"termination":result["termination"],
                        "has_solution":result["solution"] is not None,"independent_check":outcome["independent_check"],
                        "note":"Actual observation; a fast completed search is reported honestly. A deadline can retain a feasible incumbent."}
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=Path(__file__).with_name("basic-input.json"))
    parser.add_argument("--engine",choices=("both","reference","own"),default="both")
    parser.add_argument("--diagnostics",action="store_true",help="Use separate fixed synthetic failure probes")
    args=parser.parse_args()
    problem=parse_json(args.input.read_text())
    factories={"own":OwnLibraryAdapter}
    if args.engine in {"both","reference"}:
        from ocp_routing import RoutingAdapter, ORToolsBackend
        factories={"reference":lambda:RoutingAdapter(ORToolsBackend()),**factories}
    selected=list(factories) if args.engine=="both" else [args.engine]
    runs={name:run_app(factories[name](),problem,"first-success-"+name) for name in selected}
    report={"status":"PASS","scope":"local developer preview; no external trial or engine certification",
            "input_sha256":hashlib.sha256(json.dumps(problem,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "runs":runs,"diagnostics":diagnostics() if args.diagnostics else {}}
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    try:main()
    except Exception as error:
        print(json.dumps({"status":"FAIL","code":"DEMO_FAILED","detail":str(error),
                          "hint":"Use the installed environment. Check the selected engine's declared limits and your routing.basic input."}))
        raise SystemExit(1)
