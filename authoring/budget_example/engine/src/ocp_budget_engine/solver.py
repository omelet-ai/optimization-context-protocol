"""0/1 knapsack dynamic programming; no checker or reference solver imports."""
import time


def solve(problem, deadline, clock=time.monotonic):
    # Value at an exact used capacity, retaining a reconstructable incumbent.
    states = {0: (0, ())}
    for item in problem['items']:
        previous = list(states.items())
        for used, (benefit, selected) in previous:
            if clock() >= deadline:
                return {'selected': list(max(states.values(), key=lambda v: v[0])[1])}, False
            cost = used + int(item['cost'])
            value = benefit + int(item['benefit'])
            if cost <= problem['capacity'] and (cost not in states or value > states[cost][0]):
                states[cost] = (value, selected + (item['id'],))
    return {'selected': list(max(states.values(), key=lambda v: v[0])[1])}, True
