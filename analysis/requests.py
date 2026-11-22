from dataclasses import dataclass

from evidence.pieces import PieceOrigin, V1Piece
from evidence.receipts import AcceptanceReceipt


@dataclass(frozen=True)
class V1Request:
    acceptance_id: int
    piece_id: str
    origin: PieceOrigin
    marker: str
    bounds: tuple[int, int]


def prepare_v1_request(piece: V1Piece, receipt: AcceptanceReceipt, marker: str) -> V1Request:
    if receipt.piece_id != piece.piece_id or receipt.origin != piece.origin:
        raise ValueError('acceptance receipt does not describe the selected piece')
    bounds = piece.bounds_for(marker)
    return V1Request(receipt.acceptance_id, piece.piece_id, piece.origin, marker, bounds)
