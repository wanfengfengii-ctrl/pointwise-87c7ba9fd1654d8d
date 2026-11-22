from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from bench.consistency import topological_order
from bench.precedence import PrecedenceGraph


@dataclass(frozen=True)
class Reachability:
    ancestors: Mapping[str, frozenset[str]]
    successors: Mapping[str, frozenset[str]]


def transitive_closure(graph: PrecedenceGraph) -> Reachability:
    order = topological_order(graph)
    outgoing = {vertex: [] for vertex in order}
    for earlier, later in graph.edges:
        outgoing[earlier].append(later)

    ancestors = {vertex: set() for vertex in order}
    for vertex in order:
        for later in outgoing[vertex]:
            ancestors[later].add(vertex)
            ancestors[later].update(ancestors[vertex])

    successors = {vertex: set() for vertex in order}
    for vertex in reversed(order):
        for later in outgoing[vertex]:
            successors[vertex].add(later)
            successors[vertex].update(successors[later])

    return Reachability(
        MappingProxyType({vertex: frozenset(ancestors[vertex]) for vertex in order}),
        MappingProxyType({vertex: frozenset(successors[vertex]) for vertex in order}),
    )
