from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from bench.observations import ReadingInterval
from panel.markers import validate_identifier


@dataclass(frozen=True)
class PrecedenceGraph:
    vertices: tuple[str, ...]
    inferred_edges: tuple[tuple[str, str], ...]
    certified_edges: tuple[tuple[str, str], ...]

    @property
    def edges(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(set(self.inferred_edges).union(self.certified_edges)))


def build_precedence(readings: tuple[tuple[str, ReadingInterval], ...],
                     certificates: Iterable = ()) -> PrecedenceGraph:
    vertices = tuple(name for name, _ in readings)
    inferred = []
    for (left, a), (right, b) in combinations(readings, 2):
        if a.upper < b.lower:
            inferred.append((left, right))
        elif b.upper < a.lower:
            inferred.append((right, left))

    allowed = set(vertices)
    certified = set()
    try:
        certificates = iter(certificates)
    except TypeError as exc:
        raise ValueError('certificates must contain ordered specimen pairs') from exc
    for edge in certificates:
        if not isinstance(edge, (tuple, list)) or len(edge) != 2:
            raise ValueError('a certificate requires two specimen identities')
        earlier, later = map(validate_identifier, edge)
        if earlier not in allowed or later not in allowed:
            raise ValueError('certificate endpoint outside the tray roster')
        certified.add((earlier, later))
    return PrecedenceGraph(vertices, tuple(sorted(inferred)), tuple(sorted(certified)))
