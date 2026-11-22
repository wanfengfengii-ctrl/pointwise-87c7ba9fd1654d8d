import sqlite3

from evidence.codec import decode_v1, encode_v1
from evidence.pieces import V1Piece
from reports.transactions import write_transaction


def initialize_issued_pieces(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS issued_v1 (
        piece_id TEXT PRIMARY KEY NOT NULL,
        revision_id INTEGER NOT NULL REFERENCES bench_revisions(revision_id),
        payload TEXT NOT NULL
    )''')


def save_issued_v1(db: sqlite3.Connection, piece: V1Piece) -> None:
    payload = encode_v1(piece)
    with write_transaction(db):
        db.execute('INSERT INTO issued_v1 VALUES (?, ?, ?)',
                   (piece.piece_id, piece.origin.revision_id, payload))


def read_issued_v1(db: sqlite3.Connection, piece_id: str) -> V1Piece:
    if not isinstance(piece_id, str) or not piece_id.isprintable():
        raise KeyError(piece_id)
    row = db.execute('SELECT payload FROM issued_v1 WHERE piece_id = ?', (piece_id,)).fetchone()
    if row is None:
        raise KeyError(piece_id)
    return decode_v1(row[0])
