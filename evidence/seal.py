import sqlite3
from uuid import uuid4

from analysis.closure import transitive_closure
from analysis.rank_bounds import marker_rank_bounds
from bench.revision_store import get_revision
from evidence.issued_store import save_issued_v1
from evidence.pieces import PieceOrigin, V1Piece, make_v1_piece


def seal_v1(db: sqlite3.Connection, revision_id: int) -> V1Piece:
    snapshot = get_revision(db, revision_id)
    roster = snapshot.roster
    markers = roster.batch.markers
    bounds = marker_rank_bounds(transitive_closure(snapshot.graph), markers)
    origin = PieceOrigin(roster.batch.batch_id, roster.tray_id, snapshot.revision_id)
    piece = make_v1_piece(uuid4().hex, origin, markers, len(roster.members), bounds)
    save_issued_v1(db, piece)
    return piece
