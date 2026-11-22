from dataclasses import dataclass

from panel.markers import MarkerPair, make_marker_pair, validate_identifier
from panel.units import require_batch_unit, validate_unit


@dataclass(frozen=True)
class Batch:
    batch_id: str
    unit: str
    markers: MarkerPair

    def require_matching_definition(self, candidate: 'Batch') -> None:
        require_batch_unit(self.unit, candidate.unit)
        if self.batch_id != candidate.batch_id or self.markers != candidate.markers:
            raise ValueError('batch identity or marker definition differs')


def make_batch(batch_id: str, markers, unit: str) -> Batch:
    return Batch(validate_identifier(batch_id), validate_unit(unit), make_marker_pair(markers))
