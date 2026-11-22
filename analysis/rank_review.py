import sqlite3
from uuid import uuid4

from analysis.proof_solver import minimal_certificates
from analysis.requests import prepare_proof_request, prepare_v1_request
from evidence.intake import read_accepted_proof, read_accepted_v1
from panel.markers import validate_identifier
from reports.issue import publish_v1
from reports.proof_records import build_report, insert_report
from reports.records import V1Report


def issue_v1(db: sqlite3.Connection, acceptance_id: int, marker: str) -> V1Report:
    piece, receipt = read_accepted_v1(db, acceptance_id)
    request = prepare_v1_request(piece, receipt, marker)
    return publish_v1(db, request)


def issue_proof(db: sqlite3.Connection, acceptance_id: str, marker: str,
                side: str, rank: int, allowed) -> dict:
    # A malformed identifier (including any V1 integer acceptance number) is a
    # request error; a well-formed but unknown identifier is a lookup failure.
    validate_identifier(acceptance_id)
    piece = read_accepted_proof(db, acceptance_id)
    request = prepare_proof_request(piece, acceptance_id, marker, side, rank, allowed)

    target = piece.node_for(request.marker)
    selection = minimal_certificates(piece, target, request.side, request.rank,
                                     list(request.allowed))
    if selection is None:
        status, certificates = 'impossible', None
    else:
        status, certificates = 'proved', selection

    report = build_report(uuid4().hex, request.acceptance_id, piece, request.marker,
                          request.side, request.rank, request.allowed, status,
                          certificates, uuid4().hex)
    insert_report(db, report)
    return report
