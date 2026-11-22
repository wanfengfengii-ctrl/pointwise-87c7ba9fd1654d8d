from collections import deque

from bench.precedence import PrecedenceGraph


def topological_order(graph: PrecedenceGraph) -> tuple[str, ...]:
    """Return a deterministic order of all vertices, or reject a cyclic union."""
    successors = {vertex: [] for vertex in graph.vertices}
    indegree = dict.fromkeys(graph.vertices, 0)
    for earlier, later in graph.edges:
        successors[earlier].append(later)
        indegree[later] += 1

    available = deque(vertex for vertex in graph.vertices if indegree[vertex] == 0)
    order = []
    while available:
        vertex = available.popleft()
        order.append(vertex)
        for later in successors[vertex]:
            indegree[later] -= 1
            if indegree[later] == 0:
                available.append(later)
    if len(order) != len(graph.vertices):
        raise ValueError('strict precedence evidence contains a cycle')
    return tuple(order)
