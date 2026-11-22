from dataclasses import dataclass

from evidence.pieces import PieceOrigin, V1Piece
from evidence.proof_models import ProofPiece
from evidence.receipts import AcceptanceReceipt
from panel.markers import validate_identifier

_SIDES = ('at_least', 'at_most')


@dataclass(frozen=True)
class V1Request:
    acceptance_id: int
    piece_id: str
    origin: PieceOrigin
    marker: str
    bounds: tuple[int, int]


@dataclass(frozen=True)
class ProofRequest:
    acceptance_id: str
    piece_id: str
    origin: PieceOrigin
    marker: str
    side: str
    rank: int
    allowed: tuple[str, ...]


def prepare_v1_request(piece: V1Piece, receipt: AcceptanceReceipt, marker: str) -> V1Request:
    if receipt.piece_id != piece.piece_id or receipt.origin != piece.origin:
        raise ValueError('acceptance receipt does not describe the selected piece')
    bounds = piece.bounds_for(marker)
    return V1Request(receipt.acceptance_id, piece.piece_id, piece.origin, marker, bounds)


def _validate_allowed(allowed, piece: ProofPiece) -> tuple[str, ...]:
    if allowed is None:
        return ()
    if isinstance(allowed, (str, bytes)) or not isinstance(allowed, (list, tuple)):
        raise ValueError('allowed must be a list or tuple of certificate identifiers')
    known = set(piece.certificate_ids)
    seen = set()
    ordered = []
    for item in allowed:
        value = validate_identifier(item)
        if value in seen:
            raise ValueError('allowed certificate identifiers must be distinct')
        if value not in known:
            raise ValueError('allowed certificate identifier is not present on this piece')
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def prepare_proof_request(piece: ProofPiece, acceptance_id: str, marker: str,
                          side: str, rank: int, allowed) -> ProofRequest:
    acceptance_id = validate_identifier(acceptance_id)
    if not isinstance(marker, str) or marker not in piece.marker_choices:
        raise ValueError('marker is not one of the two named markers on this piece')
    if side not in _SIDES:
        raise ValueError('side must be at_least or at_most')
    if type(rank) is not int or not 1 <= rank <= piece.specimen_count:
        raise ValueError('rank must be an integer within the specimen count')
    permitted = _validate_allowed(allowed, piece)
    return ProofRequest(acceptance_id, piece.piece_id, piece.origin, marker, side, rank, permitted)
