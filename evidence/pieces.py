from collections.abc import Mapping
from dataclasses import dataclass

from panel.markers import MarkerPair, make_marker_pair, validate_identifier


@dataclass(frozen=True)
class PieceOrigin:
    batch_id: str
    tray_id: str
    revision_id: int

    def __post_init__(self) -> None:
        validate_identifier(self.batch_id)
        validate_identifier(self.tray_id)
        if type(self.revision_id) is not int or not 1 <= self.revision_id < 2**63:
            raise ValueError('revision_id must be a positive SQLite identifier')


def _rank_interval(value, specimen_count: int) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('each marker requires a pair of rank bounds')
    lower, upper = value
    if type(lower) is not int or type(upper) is not int:
        raise ValueError('rank bounds must be integers')
    if not 1 <= lower <= upper <= specimen_count:
        raise ValueError('rank bounds are outside the specimen count')
    return lower, upper


@dataclass(frozen=True)
class V1Piece:
    piece_id: str
    origin: PieceOrigin
    markers: MarkerPair
    specimen_count: int
    first_bounds: tuple[int, int]
    second_bounds: tuple[int, int]

    def __post_init__(self) -> None:
        validate_identifier(self.piece_id)
        if not isinstance(self.origin, PieceOrigin) or not isinstance(self.markers, MarkerPair):
            raise ValueError('a piece requires an origin and marker pair')
        if type(self.specimen_count) is not int or self.specimen_count < 2:
            raise ValueError('specimen_count must be an integer of at least two')
        object.__setattr__(self, 'first_bounds', _rank_interval(self.first_bounds, self.specimen_count))
        object.__setattr__(self, 'second_bounds', _rank_interval(self.second_bounds, self.specimen_count))

    @property
    def rank_bounds(self) -> dict[str, tuple[int, int]]:
        return {self.markers.first: self.first_bounds, self.markers.second: self.second_bounds}

    def bounds_for(self, marker: str) -> tuple[int, int]:
        if not self.markers.contains(marker):
            raise ValueError('marker is not present on this piece')
        return self.first_bounds if marker == self.markers.first else self.second_bounds


def make_v1_piece(piece_id: str, origin: PieceOrigin, markers, specimen_count: int,
                  rank_bounds: Mapping) -> V1Piece:
    pair = make_marker_pair(markers)
    if not isinstance(rank_bounds, Mapping) or set(rank_bounds) != set(pair.as_tuple()):
        raise ValueError('rank bounds must be keyed by exactly the two marker identities')
    return V1Piece(piece_id, origin, pair, specimen_count,
                   rank_bounds[pair.first], rank_bounds[pair.second])
