"""Independent subset-partition oracle. Does not load the optimization algorithm."""
from collections import Counter
from functools import lru_cache


def minimum_by_partition(stock, pieces):
    full = (1 << len(pieces)) - 1
    sums = [0] * (full + 1)
    for mask in range(1, full + 1):
        bit = mask & -mask
        sums[mask] = sums[mask ^ bit] + pieces[bit.bit_length() - 1]

    @lru_cache(None)
    def count(mask):
        if mask == 0:
            return 0
        if sums[mask] <= stock:
            return 1
        anchor = mask & -mask
        remaining = mask ^ anchor
        subset = remaining
        best = len(pieces) + 1
        while True:
            bar = anchor | subset
            if sums[bar] <= stock:
                best = min(best, 1 + count(mask ^ bar))
            if not subset:
                return best
            subset = (subset - 1) & remaining

    return count(full)


class Checker:
    identity = {"id": "cutplan.partition-checker", "version": "1.0.0"}

    def evaluate(self, data, config, result):
        layout = result.get("cuts_cm", [])
        valid_shape = isinstance(layout, list) and all(
            isinstance(row, list) and row and all(type(x) is int and x > 0 for x in row)
            for row in layout
        )
        valid_shape = bool(valid_shape and layout)
        pieces = data["pieces_cm"]
        stock = data["stock_length_cm"]
        conditions = {
            "bar_count": valid_shape and type(result.get("stock_count")) is int and len(layout) == result["stock_count"],
            "each_piece_once": valid_shape and Counter(x for row in layout for x in row) == Counter(pieces),
            "stock_capacity": valid_shape and all(sum(row) <= stock for row in layout),
            "independent_minimum": valid_shape and len(layout) == minimum_by_partition(stock, pieces),
        }
        return {
            "status": "pass" if all(conditions.values()) else "fail",
            "checks": [{"id": name, "status": "pass" if ok else "fail"} for name, ok in conditions.items()],
            "verified_scope": list(conditions),
            "unverified": ["unsubmitted business requirements", "physical cutting loss other than zero"],
        }
