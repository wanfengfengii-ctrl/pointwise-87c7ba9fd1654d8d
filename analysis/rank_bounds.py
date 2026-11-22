from analysis.closure import Reachability
from panel.markers import MarkerPair


def marker_rank_bounds(reachability: Reachability, markers: MarkerPair) -> dict[str, tuple[int, int]]:
    """Compute each marker's inclusive, one-based interval in the entire tray."""
    population = len(reachability.ancestors)
    return {
        marker: (1 + len(reachability.ancestors[marker]),
                 population - len(reachability.successors[marker]))
        for marker in markers.as_tuple()
    }
