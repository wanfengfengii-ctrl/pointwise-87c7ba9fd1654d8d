"""Select a minimum sufficient certificate subset for one rank threshold.

Only reading-derived precedence is always active.  A manual certificate
contributes its edge only when it is selected.  The rank of a specimen over
all compatible linear orders of the revision lies in the contiguous interval
``[1 + ancestors, n - successors]``; a one-sided threshold is met exactly when
the selected edges make the relevant ancestor (or successor) closure large
enough.  Enumeration of certificate subsets is explicitly permitted.
"""
from itertools import combinations


def _reachable(nodes, edges, target, forward) -> int:
    adjacency = {node: set() for node in nodes}
    for earlier, later in edges:
        if forward:
            adjacency[earlier].add(later)
        else:
            adjacency[later].add(earlier)
    seen = set()
    stack = list(adjacency[target])
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node])
    return len(seen)


def _satisfied(nodes, base_edges, certificate_edges, target, side, rank, count) -> bool:
    edges = base_edges.union(certificate_edges)
    if side == 'at_least':
        return 1 + _reachable(nodes, edges, target, forward=False) >= rank
    return count - _reachable(nodes, edges, target, forward=True) <= rank


def minimal_certificates(piece, target: str, side: str, rank: int,
                         allowed: list[str]) -> list[str] | None:
    """Return a minimum-size sufficient subset of ``allowed``, or ``None``.

    ``None`` means even using every allowed certificate the threshold cannot be
    guaranteed.  Ties are broken by the request order, which yields the
    lexicographically first minimal subset.
    """
    nodes = piece.specimens
    base_edges = set(piece.inferred_edges)
    certificate_edges = piece.certificate_map()
    count = piece.specimen_count

    options = list(allowed)
    for size in range(len(options) + 1):
        for chosen in combinations(range(len(options)), size):
            selected = [options[index] for index in chosen]
            edges = {certificate_edges[cid] for cid in selected}
            if _satisfied(nodes, base_edges, edges, target, side, rank, count):
                return selected
    return None
