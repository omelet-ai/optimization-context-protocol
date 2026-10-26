"""Generate the website's synthetic example using installed packages, never fixtures as outputs."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
from ocp_candidate import Client
from ocp_routing import RoutingAdapter, ORToolsBackend
from conformance.routing import verify_result

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("input")
parser.add_argument("--report-ready",action="store_true",help=argparse.SUPPRESS)
args=parser.parse_args()
problem=json.loads(Path(args.input).read_text())
adapter=RoutingAdapter(ORToolsBackend())
if args.report_ready:print("OCP_SITE_ENGINE_READY",flush=True)
client=Client(adapter)
request=client.request(problem,request_id="site-routing-example")
result=client.execute(problem,request_id="site-routing-example")
checked=verify_result(request,result)
if not checked["feasible"] or checked["total_cost"]!=18:raise RuntimeError("Unexpected tiny-example result")
evaluation=adapter.evaluate(request,result["solution"])
if evaluation["kind"]!="evaluation":raise RuntimeError("Evaluation failed")
bad=deepcopy(problem);bad["load_unit"]="lb"
rejected=client.execute(bad,request_id="site-unsupported-unit")
if rejected["kind"]!="failure" or rejected["error"]["code"]!="INVALID_DATA":raise RuntimeError("Unsupported unit was not rejected")
print(json.dumps({
 "routing":{"input":problem,"request":request,"result":result,"evaluation":evaluation,"independent_check":checked,
            "summary":"Feasible route · total cost 18 meters · capacity and visit coverage independently checked. No optimality claim."},
 "rejected":{"input":bad,"result":rejected,"evaluation":None,
             "summary":"INVALID_DATA · unsupported load unit rejected before solving. No result to evaluate."}
},ensure_ascii=False))
