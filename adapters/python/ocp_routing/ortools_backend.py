"""Actual OR-Tools CVRP library call; no external service or fallback solver."""

from dataclasses import dataclass
from importlib.metadata import version
from typing import Optional


@dataclass
class Outcome:
    solution: Optional[dict]
    termination: str
    objective: Optional[int]


class ORToolsBackend:
    name = "ortools.routing"

    def __init__(self):
        self.version = version("ortools")

    def solve(self, problem, time_limit_ms):
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        names = problem["matrix"]["node_ids"]
        matrix = problem["matrix"]["values"]
        depot = names.index(problem["depot"])
        vehicles = problem["vehicles"]
        demand = {v["id"]:int(v["demand"]) for v in problem["visits"]}
        manager = pywrapcp.RoutingIndexManager(len(names), len(vehicles), depot)
        routing = pywrapcp.RoutingModel(manager)

        def distance(a,b):
            return int(matrix[manager.IndexToNode(a)][manager.IndexToNode(b)])

        distance_index = routing.RegisterTransitCallback(distance)
        routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
        demand_index = routing.RegisterUnaryTransitCallback(lambda index: demand.get(names[manager.IndexToNode(index)],0))
        routing.AddDimensionWithVehicleCapacity(demand_index, 0, [int(v["capacity"]) for v in vehicles], True, "WeightCapacity")
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT
        params.time_limit.FromMilliseconds(int(time_limit_ms))
        answer = routing.SolveWithParameters(params)
        status = routing.status()
        # No result from search is not an infeasibility certificate.
        if answer is None:
            if status == 5:
                raise RuntimeError("OR-Tools model was rejected")
            return Outcome(None,"time_limit" if status==4 else "search_exhausted",None)
        routes=[]
        for vehicle_index, vehicle in enumerate(vehicles):
            position = routing.Start(vehicle_index)
            visits=[]
            while not routing.IsEnd(position):
                node=manager.IndexToNode(position)
                if node != depot:
                    visits.append(names[node])
                position=answer.Value(routing.NextVar(position))
            routes.append({"vehicle_id":vehicle["id"],"visits":visits})
        return Outcome({"routes":routes},"time_limit" if status==2 else "completed",int(answer.ObjectiveValue()))
