from dataclasses import dataclass

from evidence.pieces import PieceOrigin, V1Piece


@dataclass(frozen=True)
class AcceptanceReceipt:
    acceptance_id: int
    piece_id: str
    origin: PieceOrigin


def make_acceptance_receipt(acceptance_id: int, piece: V1Piece) -> AcceptanceReceipt:
    return AcceptanceReceipt(acceptance_id, piece.piece_id, piece.origin)
