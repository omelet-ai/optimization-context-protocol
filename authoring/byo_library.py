"""Small actual engine example. Replace this library while preserving the declared profile."""

from itertools import permutations, product
import time
from ocp_candidate import Client, OCPError
from ocp_candidate.contract import failure
from ocp_routing import RoutingAdapter
from ocp_routing.ortools_backend import Outcome


class EnumeratingLibrary:
    name="example.enumerating-library"
    version="0.1.0"

    def solve(self, problem, time_limit_ms):
        deadline=time.monotonic()+time_limit_ms/1000
        visits=problem["visits"]; vehicles=problem["vehicles"]
        positions={name:i for i,name in enumerate(problem["matrix"]["node_ids"])}
        matrix=problem["matrix"]["values"]
        best_solution=None; best_cost=None
        for assignment in product(range(len(vehicles)),repeat=len(visits)):
            if time.monotonic()>=deadline: return Outcome(best_solution,"time_limit",best_cost)
            groups=[[visit for visit,owner in zip(visits,assignment) if owner==i] for i in range(len(vehicles))]
            if any(sum(visit["demand"] for visit in group)>vehicle["capacity"] for group,vehicle in zip(groups,vehicles)): continue
            total=0; routes=[]
            for group,vehicle in zip(groups,vehicles):
                route_best=None; route_cost=None
                for order in permutations(group):
                    if time.monotonic()>=deadline: return Outcome(best_solution,"time_limit",best_cost)
                    names=[problem["depot"]]+[v["id"] for v in order]+[problem["depot"]]
                    cost=sum(matrix[positions[a]][positions[b]] for a,b in zip(names,names[1:]))
                    if route_cost is None or cost<route_cost:
                        route_cost=cost; route_best=names[1:-1]
                total+=route_cost
                routes.append({"vehicle_id":vehicle["id"],"visits":route_best})
            if best_cost is None or total<best_cost:
                best_cost=total; best_solution={"routes":routes}
        # Adapter conservatively reports feasible/unknown; this example issues no proof certificate.
        return Outcome(best_solution,"completed" if best_solution is not None else "search_exhausted",best_cost)


class OwnLibraryAdapter(RoutingAdapter):
    def __init__(self):
        super().__init__(EnumeratingLibrary())
        self.identity={"id":"example.own-routing", "version":"0.1.0"}

    def describe(self):
        value=super().describe()
        value["limitations"]=["Teaching library: at most 6 visits and 3 vehicles, budget at most 5000 ms",
                              "Explicit integer meter matrix and kg, same routing.basic semantics",
                              "No OR-Tools/Omelet dependency, remote service, or optimality certificate"]
        return value

    def validate(self, request):
        value=super().validate(request)
        if value["valid"] and (len(request["input"]["visits"])>6 or len(request["input"]["vehicles"])>3):
            value["valid"]=False
            value["issues"]=[{"code":"LIMIT_EXCEEDED","path":"/input","message":"Teaching library supports at most 6 visits and 3 vehicles"}]
        return value

    def execute(self, request):
        checked=self.validate(request)
        if not checked["valid"]:
            issue=checked["issues"][0]
            return failure(checked["request_id"],OCPError(issue["code"],issue["path"],issue["message"]))
        return super().execute(request)


if __name__=="__main__":
    import argparse,json
    from pathlib import Path
    from ocp_candidate import parse_json
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("input")
    parser.add_argument("--trace",help="Save request/response to a new file for independent conformance")
    args=parser.parse_args()
    try:
        problem=parse_json(Path(args.input).read_text())
        client=Client(OwnLibraryAdapter())
        request=client.request(problem,request_id="byo-library")
        result=client.execute(problem,request_id="byo-library")
        if args.trace:
            with open(args.trace,"x") as stream:json.dump({"request":request,"response":result},stream)
    except (OSError, UnicodeError, OCPError) as error:
        result=failure("byo-library",error if isinstance(error,OCPError) else OCPError("INPUT_UNREADABLE",message="Check the UTF-8 JSON input path"))
    print(json.dumps(result))
    raise SystemExit(2 if result["kind"]=="failure" else 0)
