import sqlite3
from uuid import uuid4

from evidence.codec import decode_v1, encode_v1
from evidence.pieces import V1Piece
from evidence.proof_codec import decode_v2, encode_v2
from evidence.proof_models import ProofPiece
from evidence.receipts import AcceptanceReceipt, make_acceptance_receipt
from reports.transactions import write_transaction


def initialize_intake(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS accepted_v1 (
        acceptance_id INTEGER PRIMARY KEY,
        piece_id TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS accepted_v2 (
        acceptance_id TEXT PRIMARY KEY NOT NULL,
        piece_id TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL
    )''')


def accept_v1(db: sqlite3.Connection, text: str) -> AcceptanceReceipt:
    piece = decode_v1(text)
    payload = encode_v1(piece)
    with write_transaction(db):
        saved = db.execute('SELECT acceptance_id, payload FROM accepted_v1 WHERE piece_id = ?',
                           (piece.piece_id,)).fetchone()
        if saved is None:
            inserted = db.execute('INSERT INTO accepted_v1 (piece_id, payload) VALUES (?, ?)',
                                  (piece.piece_id, payload))
            acceptance_id = inserted.lastrowid
        else:
            acceptance_id, prior_payload = saved
            if decode_v1(prior_payload) != piece:
                raise ValueError('piece identity already has different content')
    return make_acceptance_receipt(acceptance_id, piece)


def read_accepted_v1(db: sqlite3.Connection, acceptance_id: int) -> tuple[V1Piece, AcceptanceReceipt]:
    if type(acceptance_id) is not int or not 1 <= acceptance_id < 2**63:
        raise KeyError(acceptance_id)
    row = db.execute('SELECT payload FROM accepted_v1 WHERE acceptance_id = ?',
                     (acceptance_id,)).fetchone()
    if row is None:
        raise KeyError(acceptance_id)
    piece = decode_v1(row[0])
    return piece, make_acceptance_receipt(acceptance_id, piece)


def accept_proof(db: sqlite3.Connection, text: str) -> str:
    """Validate and pin a V2 piece, returning its centre text acceptance number."""
    piece = decode_v2(text)
    payload = encode_v2(piece)
    with write_transaction(db):
        saved = db.execute('SELECT acceptance_id, payload FROM accepted_v2 WHERE piece_id = ?',
                           (piece.piece_id,)).fetchone()
        if saved is None:
            acceptance_id = uuid4().hex
            db.execute('INSERT INTO accepted_v2 (acceptance_id, piece_id, payload) VALUES (?, ?, ?)',
                       (acceptance_id, piece.piece_id, payload))
        else:
            acceptance_id, prior_payload = saved
            if decode_v2(prior_payload) != piece:
                raise ValueError('piece identity already has different content')
    return acceptance_id


def read_accepted_proof(db: sqlite3.Connection, acceptance_id: str) -> ProofPiece:
    if not _is_text(acceptance_id):
        raise KeyError(acceptance_id)
    row = db.execute('SELECT payload FROM accepted_v2 WHERE acceptance_id = ?',
                     (acceptance_id,)).fetchone()
    if row is None:
        raise KeyError(acceptance_id)
    return decode_v2(row[0])


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.isprintable()
