"""Minimum identical stock bars, integer lengths, zero cutting loss. No OCP imports."""


def pack(stock_length, pieces):
    if type(stock_length) is not int or not 1 <= stock_length <= 100_000:
        raise ValueError("stock length must be a positive integer up to 100000")
    if not 1 <= len(pieces) <= 12 or any(type(p) is not int or not 1 <= p <= 100_000 for p in pieces):
        raise ValueError("expected one to twelve positive integer pieces up to 100000")
    if max(pieces) > stock_length:
        return None

    # For a fixed set of pieces, fewer bars dominates. At the same count,
    # a lighter last bar always leaves at least as much space for the next piece.
    states = {0: (0, 0)}
    parents = {}
    for mask in range(1, 1 << len(pieces)):
        best = None
        for index, length in enumerate(pieces):
            bit = 1 << index
            if not mask & bit:
                continue
            previous = mask ^ bit
            bars, used = states[previous]
            starts_bar = bars == 0 or used + length > stock_length
            candidate = (bars + 1, length) if starts_bar else (bars, used + length)
            if best is None or candidate < best:
                best = candidate
                parents[mask] = (previous, index, starts_bar)
        states[mask] = best

    steps = []
    mask = (1 << len(pieces)) - 1
    while mask:
        mask, index, starts_bar = parents[mask]
        steps.append((pieces[index], starts_bar))
    layout = []
    for length, starts_bar in reversed(steps):
        if starts_bar:
            layout.append([])
        layout[-1].append(length)
    return layout
