import sqlite3
from uuid import uuid4

from analysis.closure import transitive_closure
from analysis.rank_bounds import marker_rank_bounds
from bench.revision_store import get_revision
from evidence.issued_store import save_issued_v1, save_issued_v2
from evidence.pieces import PieceOrigin, V1Piece, make_v1_piece
from evidence.proof_codec import encode_v2
from evidence.proof_models import local_specimen_labels, make_proof_piece


def seal_v1(db: sqlite3.Connection, revision_id: int) -> V1Piece:
    snapshot = get_revision(db, revision_id)
    roster = snapshot.roster
    markers = roster.batch.markers
    bounds = marker_rank_bounds(transitive_closure(snapshot.graph), markers)
    origin = PieceOrigin(roster.batch.batch_id, roster.tray_id, snapshot.revision_id)
    piece = make_v1_piece(uuid4().hex, origin, markers, len(roster.members), bounds)
    save_issued_v1(db, piece)
    return piece


def seal_proof(db: sqlite3.Connection, revision_id: int) -> tuple[str, dict]:
    """Issue a V2 proof piece pinned to one exact revision.

    Returns ``(text, local_certificates)`` where ``local_certificates`` maps
    each piece-local certificate identifier to the original
    ``(earlier, later)`` specimen pair.  The mapping never leaves the source
    database; both the text and the mapping are committed before returning.
    """
    snapshot = get_revision(db, revision_id)
    roster = snapshot.roster
    markers = roster.batch.markers
    origin = PieceOrigin(roster.batch.batch_id, roster.tray_id, snapshot.revision_id)

    labels = local_specimen_labels(roster.members, markers)
    specimen_labels = tuple(labels[member] for member in roster.members)
    marker_nodes = tuple((marker, labels[marker]) for marker in markers.as_tuple())
    inferred = tuple(sorted((labels[earlier], labels[later])
                            for earlier, later in snapshot.graph.inferred_edges))

    certificate_edges = []
    local_certificates = {}
    for earlier, later in snapshot.graph.certified_edges:
        certificate_id = uuid4().hex
        certificate_edges.append((certificate_id, labels[earlier], labels[later]))
        local_certificates[certificate_id] = (earlier, later)

    piece = make_proof_piece(
        uuid4().hex, origin, markers, len(roster.members),
        tuple(cid for cid, _, _ in certificate_edges),
        specimen_labels, marker_nodes, inferred, tuple(certificate_edges),
    )
    text = encode_v2(piece)
    save_issued_v2(db, piece, text, local_certificates)
    return text, local_certificates
